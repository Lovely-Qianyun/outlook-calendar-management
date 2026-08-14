"""ocal_time 的测试。

被测模块 ocal_time 负责三件事，是所有命令的时间底座：
- _parse_dt_arg 解析并校验命令行时间参数，格式错在这里抛 CalError
- _parse_dt / _resolve_tz / _normalize_dt 解析 Graph 返回的时间字符串并做时区换算
- _all_day_range / _fmt / _weekday 计算全天事件日期段、格式化时间与星期

为什么这个模块值得重点盯：时区解析失败会静默回退 UTC，日程时间直接偏几小时；
时间格式校验不严则坏数据会一路进到 Graph 请求里。下面的测试按这三个职责组织。
"""
from datetime import datetime, timezone

import pytest

from ocal_errors import CalError
from ocal_time import (
    _parse_dt_arg, _all_day_range, _normalize_dt, _parse_dt,
    _resolve_tz, _fmt, _weekday, _mk_tz, _tz_from_env, _tz_from_offset,
    _local_time_exists, _POSIX_TZ,
)


class TestLocalTimeExists:
    """夏令时跳变检测 _local_time_exists（测试注入美东时区，不依赖本机）。"""

    from zoneinfo import ZoneInfo as _ZI

    def test_nonexistent_spring_forward(self):
        """美东 2026-03-08 02:30 被跳变跳过：判定不存在。"""
        assert _local_time_exists(datetime(2026, 3, 8, 2, 30),
                                  self._ZI("America/New_York")) is False

    def test_ambiguous_fall_back_ok(self):
        """美东 2026-11-01 01:30 是歧义时间（两个时刻都合法）：不告警。"""
        assert _local_time_exists(datetime(2026, 11, 1, 1, 30),
                                  self._ZI("America/New_York")) is True

    def test_normal_time_exists(self):
        """普通日的 02:30 存在，不误报。"""
        assert _local_time_exists(datetime(2026, 8, 10, 2, 30),
                                  self._ZI("America/New_York")) is True


class TestRelativeDate:
    """相对时间参数解析（今天/明天/本周X/中文时刻…）。

    换算基准是"运行时刻的系统时钟"（now 可注入）："今天"这类词由命令解析
    而不是 agent 凭上下文推算——这正是"创建到昨天"事故的根治点。
    """

    NOW = datetime(2026, 8, 14)  # 周五

    @pytest.mark.parametrize("s,expect", [
        ("今天", datetime(2026, 8, 14)),
        ("今日", datetime(2026, 8, 14)),
        ("明天", datetime(2026, 8, 15)),
        ("明日", datetime(2026, 8, 15)),
        ("后天", datetime(2026, 8, 16)),
        ("today", datetime(2026, 8, 14)),
        ("tomorrow", datetime(2026, 8, 15)),
        ("day after tomorrow", datetime(2026, 8, 16)),
    ])
    def test_basic(self, s, expect):
        """纯日期相对词按基准日换算。"""
        assert _parse_dt_arg(s, now=self.NOW) == expect

    @pytest.mark.parametrize("s,expect", [
        ("今天 14:00", datetime(2026, 8, 14, 14, 0)),
        ("明天 9:00", datetime(2026, 8, 15, 9, 0)),
        ("今天下午2点", datetime(2026, 8, 14, 14, 0)),
        ("今天下午2点半", datetime(2026, 8, 14, 14, 30)),
        ("明天上午9点半", datetime(2026, 8, 15, 9, 30)),
        ("今天中午12点", datetime(2026, 8, 14, 12, 0)),
        ("今天晚上8点", datetime(2026, 8, 14, 20, 0)),
        ("后天凌晨1点", datetime(2026, 8, 16, 1, 0)),
    ])
    def test_with_time(self, s, expect):
        """相对日期 + 时刻（24 小时制或中文"X点/X点半"）。"""
        assert _parse_dt_arg(s, now=self.NOW) == expect

    def test_weekday_this(self):
        """本周X 按周一起始：NOW=周五时本周五=今天。"""
        assert _parse_dt_arg("本周五", now=self.NOW) == datetime(2026, 8, 14)
        assert _parse_dt_arg("本周一", now=self.NOW) == datetime(2026, 8, 10)
        assert _parse_dt_arg("本周日", now=self.NOW) == datetime(2026, 8, 16)
        assert _parse_dt_arg("这周五", now=self.NOW) == datetime(2026, 8, 14)
        assert _parse_dt_arg("本周五 14:00", now=self.NOW) == datetime(2026, 8, 14, 14, 0)
        assert _parse_dt_arg("this friday", now=self.NOW) == datetime(2026, 8, 14)

    def test_weekday_next(self):
        """下周X = 下周的对应星期。"""
        assert _parse_dt_arg("下周三", now=self.NOW) == datetime(2026, 8, 19)
        assert _parse_dt_arg("下周周一", now=self.NOW) == datetime(2026, 8, 17)
        assert _parse_dt_arg("下周一 09:00", now=self.NOW) == datetime(2026, 8, 17, 9, 0)
        assert _parse_dt_arg("next friday", now=self.NOW) == datetime(2026, 8, 21)

    def test_monday_basis(self):
        """基准日是周一时：本周五=同一周的周五，下周五=下一周。"""
        monday = datetime(2026, 8, 10)
        assert _parse_dt_arg("本周五", now=monday) == datetime(2026, 8, 14)
        assert _parse_dt_arg("下周五", now=monday) == datetime(2026, 8, 21)

    def test_date_only_relative(self):
        """date_only 模式：相对词可用，但带时刻的相对词要拒绝。"""
        assert _parse_dt_arg("今天", now=self.NOW, date_only=True) == datetime(2026, 8, 14)
        assert _parse_dt_arg("本周五", now=self.NOW, date_only=True) == datetime(2026, 8, 14)
        with pytest.raises(CalError):
            _parse_dt_arg("今天 14:00", now=self.NOW, date_only=True)
        with pytest.raises(CalError):
            _parse_dt_arg("今天下午2点", now=self.NOW, date_only=True)

    @pytest.mark.parametrize("bad", [
        "今天abc", "本周", "周三", "下周三下午", "下午2点", "今天 25:00",
    ])
    def test_garbage_raises(self, bad):
        """不完整/歧义/超界的相对表达必须报错，不能瞎猜。"""
        with pytest.raises(CalError):
            _parse_dt_arg(bad, now=self.NOW)


class TestParseDtArg:
    """命令行时间参数解析 _parse_dt_arg。

    add/update 的开始结束时间、list/free 的日期都从它进。解析策略是：
    格式宽松（小时/月份不补零、日期缺位都收下），非法值统一抛 CalError，
    由上层转成 ❌ 开头的友好提示而不是 traceback。
    """

    def test_date_only(self):
        """纯日期参数，date_only=True 只认 YYYY-MM-DD。

        全天日程的开始时间就走这条路径，解析结果精确到日即可。
        """
        assert _parse_dt_arg("2026-08-10", date_only=True) == datetime(2026, 8, 10)

    def test_datetime_slot(self):
        """日期加时间的参数，时段日程的标准写法。

        YYYY-MM-DD HH:MM 精确到分钟，add 的时段日程、update 改时间都用它。
        """
        assert _parse_dt_arg("2026-08-10 09:30") == datetime(2026, 8, 10, 9, 30)

    def test_hour_without_padding(self):
        """小时不补零也要能解析。

        用户习惯写 9:00 而不是 09:00，两种写法必须等价，不能因为这个报错。
        """
        assert _parse_dt_arg("2026-08-17 9:00") == datetime(2026, 8, 17, 9, 0)

    def test_month_without_padding(self):
        """月份不补零也要能解析，2026-8-17 等价于 2026-08-17。"""
        assert _parse_dt_arg("2026-8-17 09:00") == datetime(2026, 8, 17, 9, 0)

    def test_single_digit_day_accepted(self):
        """日期缺位（2026-08-1）按宽松处理接受。

        这是有意的宽松，而不是遗漏：date_only 场景只取前 10 位，
        缺位日期在 strptime 里天然合法。
        """
        assert _parse_dt_arg("2026-08-1").date() == datetime(2026, 8, 1).date()

    @pytest.mark.parametrize("bad", [
        "",                       # 空
        "2026-13-01",             # 13 月
        "2026-02-30",             # 2 月 30 日
        "2026-08-17 24:00",       # 24 点
        "2026-08-17 09:60",       # 60 分
        "2026/08/10",             # 斜杠格式
        "下周三下午",              # 自然语言
    ])
    def test_invalid_formats_raise(self, bad):
        """各种非法格式都必须抛 CalError。

        覆盖空串、越界的月/日、越界的时/分、错误分隔符、自然语言表达。
        这些是用户在命令行最常见的错误输入，报错文案由语言表提供。
        """
        with pytest.raises(CalError):
            _parse_dt_arg(bad)

    def test_date_only_rejects_time(self):
        """date_only 模式拒绝带时间的输入。

        全天日程的日期参数不该混入时刻，混了说明用户搞混了参数语义，要提示。
        """
        with pytest.raises(CalError):
            _parse_dt_arg("2026-08-10 09:00", date_only=True)


class TestAllDayRange:
    """全天事件的日期段计算 _all_day_range。

    Graph 对全天事件有个固定约定：start 恒为 00:00:00，end 是末次次日 00:00（不含）。
    这个函数把 Graph 的字符串还原成用户眼中的日期段，返回的结束日期是含当天的，
    这是后续所有全天显示（列表、详情、冲突、空闲计算）的公共口径。
    """

    def test_single_day(self):
        """单天事件：start 08-10、end 08-11，实际占用就是 08-10 一天。"""
        s, e = _all_day_range("2026-08-10T00:00:00", "2026-08-11T00:00:00")
        assert (s, e) == (datetime(2026, 8, 10).date(), datetime(2026, 8, 10).date())

    def test_multi_day(self):
        """跨天事件：end 08-13 表示占到 08-12 为止。

        同时覆盖带 .0000000 小数后缀的字符串——Graph 实际返回常带这个后缀，
        取前 10 位规避。
        """
        s, e = _all_day_range("2026-08-10T00:00:00.0000000", "2026-08-13T00:00:00")
        assert (s, e) == (datetime(2026, 8, 10).date(), datetime(2026, 8, 12).date())

    def test_end_not_before_start(self):
        """end 与 start 同天时兜底为单天。

        防御 Graph 返回异常数据时不会算出负区间，显示层就不用特判。
        """
        s, e = _all_day_range("2026-08-10T00:00:00", "2026-08-10T00:00:00")
        assert (s, e) == (datetime(2026, 8, 10).date(), datetime(2026, 8, 10).date())


class TestNormalizeDt:
    """Graph 时间字符串归一化 _normalize_dt。

    Graph 返回的时间戳有两种坑：结尾带 Z（ISO 8601 的 UTC 标记），
    以及 7 位小数——Python 3.11 之前的 fromisoformat 只认 6 位。
    这个函数在 _parse_dt 之前把字符串修好。
    """

    def test_z_replaced(self):
        """结尾的 Z 换成 +00:00，fromisoformat 才认这种写法。"""
        assert _normalize_dt("2026-08-10T09:00:00Z") == "2026-08-10T09:00:00+00:00"

    def test_fraction_truncated_to_six(self):
        """7 位小数截断到 6 位，兼容低版本 Python 的解析器。"""
        assert _normalize_dt("2026-08-10T09:00:00.1234567") == "2026-08-10T09:00:00.123456"

    def test_fraction_with_offset_kept(self):
        """截断小数时必须保留时区偏移后缀。

        曾有的 bug：7 位小数 + 偏移同时出现时偏移被吞掉，
        时间被当成 naive 重新解释，日程时间直接偏移。
        """
        assert _normalize_dt("2026-08-10T09:00:00.1234567+08:00") == "2026-08-10T09:00:00.123456+08:00"

    def test_fraction_with_z_kept(self):
        """截断小数时保留 Z 转换后的 +00:00。"""
        assert _normalize_dt("2026-08-10T09:00:00.1234567Z") == "2026-08-10T09:00:00.123456+00:00"


class TestMkTz:
    """探测到的时区名 → (tzinfo, Graph 名) _mk_tz。

    全量 CLDR 映射后的抽查：官方 Windows 名解析成正确 IANA 时区，
    传给 Graph 的名字优先用 Windows 官方名；解析不了的返回 None。
    """

    def test_windows_name_roundtrip(self):
        """Windows 名解析正确，且传给 Graph 的名字保持 Windows 官方名。"""
        zi, gname = _mk_tz("US Mountain Standard Time")
        assert gname == "US Mountain Standard Time"
        assert zi.key == "America/Phoenix"  # 亚利桑那：UTC-7 无夏令时

    def test_iana_name_maps_to_windows(self):
        """IANA 名传给 Graph 时反查成 Windows 官方名。"""
        zi, gname = _mk_tz("Asia/Hong_Kong")
        assert gname == "China Standard Time"
        assert zi == _resolve_tz("Asia/Hong_Kong")

    def test_unknown_returns_none(self):
        """解析不了返回 None，交给探测链的下一级。"""
        assert _mk_tz("Mars/Phobos") is None
        assert _mk_tz("") is None


class TestTzFromEnv:
    """TZ 环境变量探测 _tz_from_env（探测链第一优先级）。"""

    def test_iana_name(self, monkeypatch):
        """TZ=IANA 名直接可用。"""
        monkeypatch.setenv("TZ", "Asia/Shanghai")
        zi, gname = _tz_from_env()
        assert gname == "China Standard Time"
        assert zi == _resolve_tz("Asia/Shanghai")

    def test_utc_variants(self, monkeypatch):
        """TZ=UTC/GMT 归一成 UTC。"""
        for v in ("UTC", "GMT"):
            monkeypatch.setenv("TZ", v)
            zi, gname = _tz_from_env()
            assert gname == "UTC"

    @pytest.mark.parametrize("v", ["CST-8", "FOO-3", ":Asia/Shanghai", "/usr/share/zoneinfo/Asia/Shanghai"])
    def test_posix_rule_string_returns_sentinel(self, monkeypatch, v):
        """POSIX 规则串（CST-8/FOO-3/带冒号/绝对路径）返回哨兵。

        TZ 一旦设置就是权威配置：探测链看到哨兵会直接走运行时偏移兜底，
        绝不能再读 /etc 下的另一套时区配置（否则解析出矛盾的时区）。
        """
        monkeypatch.setenv("TZ", v)
        assert _tz_from_env() is _POSIX_TZ

    @pytest.mark.parametrize("v,win", [
        ("EST5EDT", "Eastern Standard Time"),
        ("CST6CDT", "Central Standard Time"),
        ("Hongkong", "China Standard Time"),
    ])
    def test_legacy_alias_maps_to_windows(self, monkeypatch, v, win):
        """tzdata 旧别名（backward 链接）反查成对应 Windows 官方名。

        注意：个别链接（如 JST-9）不在 PyPI tzdata 包内，那些值会走
        哨兵 → 偏移兜底路径，同样得到正确结果（日本无夏令时）。
        """
        monkeypatch.setenv("TZ", v)
        zi, gname = _tz_from_env()
        assert gname == win

    def test_unset(self, monkeypatch):
        """没设 TZ 返回 None，交给下一级探测。"""
        monkeypatch.delenv("TZ", raising=False)
        assert _tz_from_env() is None


class TestTzFromOffset:
    """偏移兜底 _tz_from_offset：推导 Etc/GMT±N（符号与偏移相反）。

    函数接受可注入的 now 参数（datetime 是不可变 C 类型没法 monkeypatch），
    测试传固定偏移的假对象，不依赖本机时区。
    """

    def _fake_now(self, hours, minutes=0):
        from datetime import timedelta

        class _FakeNow:
            def astimezone(self):
                class _TZ:
                    def utcoffset(self):
                        return timedelta(hours=hours, minutes=minutes)
                return _TZ()
        return _FakeNow()

    def test_positive_offset(self):
        """UTC+8 推导成 Etc/GMT-8（Etc 符号与 UTC 偏移相反）。"""
        zi, gname = _tz_from_offset(self._fake_now(8))
        assert gname == "Etc/GMT-8"
        assert zi.utcoffset(None).total_seconds() == 8 * 3600

    def test_negative_offset(self):
        """UTC-5 推导成 Etc/GMT+5。"""
        zi, gname = _tz_from_offset(self._fake_now(-5))
        assert gname == "Etc/GMT+5"
        assert zi.utcoffset(None).total_seconds() == -5 * 3600

    def test_zero_offset(self):
        """零偏移归一成 UTC。"""
        zi, gname = _tz_from_offset(self._fake_now(0))
        assert gname == "UTC"

    def test_half_hour_offset_unsupported(self):
        """半小时偏移（印度等）没有 Etc 名字，返回 None 交给最终兜底。"""
        assert _tz_from_offset(self._fake_now(5, 30)) is None


class TestResolveTz:
    """时区字符串解析 _resolve_tz。

    Graph 返回的 timeZone 经常是 Windows 时区名（如 China Standard Time），
    必须先查 WINDOWS_TZ_MAP 映射成 IANA 名再交给 zoneinfo。
    解析不了的时区警告一次并回退 UTC——这正是"日程时间差几小时"问题的根源，
    所以这里专门盯住兜底行为。
    """

    def test_windows_name_mapped(self):
        """Windows 时区名和 IANA 名必须解析成同一个 tzinfo。"""
        assert _resolve_tz("China Standard Time") == _resolve_tz("Asia/Shanghai")

    @pytest.mark.parametrize("win,iana", [
        ("US Mountain Standard Time", "America/Phoenix"),        # 亚利桑那（无夏令时）
        ("Romance Standard Time", "Europe/Paris"),               # 巴黎的官方名
        ("Central Europe Standard Time", "Europe/Budapest"),     # UTC+1 无夏令时
        ("E. Europe Standard Time", "Europe/Chisinau"),
        ("FLE Standard Time", "Europe/Kyiv"),
        ("Sao Tome Standard Time", "Africa/Sao_Tome"),
        ("Magallanes Standard Time", "America/Punta_Arenas"),
        ("Lord Howe Standard Time", "Australia/Lord_Howe"),
        ("Chatham Islands Standard Time", "Pacific/Chatham"),
        ("Line Islands Standard Time", "Pacific/Kiritimati"),
        ("UTC-08", "Etc/GMT+8"),
        ("UTC+12", "Etc/GMT-12"),
    ])
    def test_full_clrd_map_samples(self, win, iana):
        """全量 CLDR 映射抽查：官方 Windows 名都必须解析到正确 IANA 时区。

        曾有的 bug：映射表只覆盖约 40 个常用时区，表外的官方时区名
        （如 US Mountain Standard Time）会静默回退 UTC，显示时间偏移几小时。
        """
        assert _resolve_tz(win) == _resolve_tz(iana)

    @pytest.mark.parametrize("legacy,iana", [
        ("Indochina Time", "Asia/Bangkok"),
        ("Malay Peninsula Standard Time", "Asia/Kuala_Lumpur"),
    ])
    def test_legacy_windows_names_still_resolve(self, legacy, iana):
        """XP 时代的废弃 Windows 时区名仍要能解析（只做解析方向，不参与反查）。"""
        assert _resolve_tz(legacy) == _resolve_tz(iana)

    @pytest.mark.parametrize("s", ["UTC", "GMT", "Z", "utc"])
    def test_utc_variants(self, s):
        """UTC 的几种写法（大写/小写/GMT/Z）都归一成 UTC。"""
        assert _resolve_tz(s) == timezone.utc

    def test_empty_falls_back_utc(self):
        """空字符串按 UTC 处理。

        Graph 偶尔不返回 timeZone 字段，字段缺失不能当作异常。
        """
        assert _resolve_tz("") == timezone.utc

    def test_unknown_tz_warns_and_falls_back(self, capsys):
        """未知时区：警告一次（按名称去重）并回退 UTC，而不是崩溃。

        警告走 stderr，用户能看到"未知时区"的提示，但日程照常显示。
        """
        tz = _resolve_tz("Mars/Phobos")
        assert tz == timezone.utc
        assert "Mars/Phobos" in capsys.readouterr().err


class TestParseDt:
    """Graph 时间字符串转本地 datetime _parse_dt。

    事件显示、冲突检测、空闲计算全部依赖它。带偏移的字符串直接解析，
    不带偏移的用事件自带的 timeZone 补全，最后统一转成本地时区，
    保证同一时刻在所有事件之间可比。
    """

    def test_naive_with_offset(self):
        """带偏移（+08:00）的字符串直接解析成 aware datetime。"""
        dt = _parse_dt("2026-08-10T09:00:00+08:00")
        assert dt.tzinfo is not None

    def test_no_offset_uses_tz_arg(self):
        """不带偏移时用传入的时区名补齐时区信息。"""
        dt = _parse_dt("2026-08-10T09:00:00", "China Standard Time")
        assert dt.tzinfo is not None

    def test_converted_to_local_tz(self):
        """结果统一转成本地时区：+08:00 的 09:00 对应 UTC 是 01:00。

        时区换算的正确性是"时间不对"问题的最后一道防线。
        """
        dt = _parse_dt("2026-08-10T09:00:00+08:00")
        assert dt.astimezone(timezone.utc).hour == 1


class TestFmt:
    """时间显示格式化 _fmt，输出 MM/DD HH:MM。

    列表、详情里所有时间显示都走它。解析不了的数据原样返回——
    宁可显示原始字符串，也不能让一条坏数据炸掉整个列表。
    """

    def test_formats_normally(self):
        """正常时间格式化成 08/10 09:00 这种样子。"""
        assert _fmt("2026-08-10T09:00:00+08:00") == "08/10 09:00"

    def test_garbage_returned_as_is(self):
        """解析不了的原样返回，保证列表展示不崩。"""
        assert _fmt("垃圾数据") == "垃圾数据"

    def test_empty_returns_empty(self):
        """空字符串返回空串。"""
        assert _fmt("") == ""


class TestWeekday:
    """星期显示 _weekday，跟随当前语言（周一 / Mon）。

    列表按天分组、详情页的时间行都用到。解析失败返回空串而不是报错。
    """

    def test_chinese(self, zh):
        """中文环境显示周几。"""
        assert _weekday("2026-08-10T09:00:00+08:00") == "周一"

    def test_english(self, en):
        """英文环境显示星期缩写。"""
        assert _weekday("2026-08-10T09:00:00+08:00") == "Mon"

    def test_garbage_returns_empty(self):
        """解析不了返回空串，不报错。"""
        assert _weekday("垃圾数据") == ""
