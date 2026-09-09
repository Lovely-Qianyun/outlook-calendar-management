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
    _local_time_exists, _POSIX_TZ, resolve_timezone,
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


class TestParseDtArg:
    """CLI 只接受补零的明确日期时间，绝不从时钟猜测或补全。"""

    @pytest.mark.parametrize("value,expected", [
        ("2026-08-10", datetime(2026, 8, 10)),
        ("2024-02-29", datetime(2024, 2, 29)),
        ("0001-01-01", datetime(1, 1, 1)),
        ("9999-12-31", datetime(9999, 12, 31)),
        ("2026-08-10 09:30", datetime(2026, 8, 10, 9, 30)),
        ("2026-08-10T09:30", datetime(2026, 8, 10, 9, 30)),
        ("2026-08-10 00:00", datetime(2026, 8, 10)),
        ("2026-08-10T23:59", datetime(2026, 8, 10, 23, 59)),
    ])
    def test_canonical_formats(self, value, expected):
        result = _parse_dt_arg(value)
        assert result == expected
        assert result.tzinfo is None

    @pytest.mark.parametrize("value", ["2026-08-10", "2024-02-29"])
    def test_date_only(self, value):
        assert _parse_dt_arg(value, date_only=True) == datetime.fromisoformat(value)

    @pytest.mark.parametrize("value", [
        "今天", "今日", "昨天", "明天", "后天", "本周五", "这周五", "下周三",
        "今天 14:00", "明天 9:00", "今天下午2点", "明天上午9点半",
        "今天中午1点", "今天上午13点", "今天晚上12点", "下个月15号",
        "today", "tomorrow", "day after tomorrow", "this friday", "next friday",
        "next friday 14:00",
    ])
    @pytest.mark.parametrize("date_only", [False, True])
    def test_natural_language_rejected(self, value, date_only):
        with pytest.raises(CalError):
            _parse_dt_arg(value, date_only=date_only)

    @pytest.mark.parametrize("value", [
        "", None, 123,
        "0000-01-01", "2026-13-01", "2026-02-29", "2026-02-30", "2026-04-31",
        "2026-08-17 24:00", "2026-08-17 09:60",
        "2026-8-17", "2026-08-1", "2026-08-17 9:00", "2026-08-17 09:0",
        "2026/08/10", "20260810", "2026-08", "08-10", "2026-W33-1",
        " 2026-08-10", "2026-08-10 ", "2026-08-10\n",
        "2026-08-10  09:00", "2026-08-10\t09:00", "2026-08-10t09:00",
        "２０２６-０８-１０", "2026-08-10 ０９:３０",
        "2026-08-10T09:00:00", "2026-08-10 09:00:00.000",
        "2026-08-10Z", "2026-08-10T09:00Z", "2026-08-10T09:00+08:00",
        "2026-08-10 09:00 Asia/Shanghai",
    ])
    def test_invalid_formats_raise(self, value):
        with pytest.raises(CalError):
            _parse_dt_arg(value)

    @pytest.mark.parametrize("value", [
        "2026-08-10 00:00", "2026-08-10T00:00", "2026-08-10 09:00",
        "2026-8-10", "2026-08-1", "2026-08-10Z",
    ])
    def test_date_only_rejects_non_dates(self, value):
        with pytest.raises(CalError):
            _parse_dt_arg(value, date_only=True)


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
    IANA 输入保留地区规则；解析不了的返回 None。
    """

    def test_windows_name_roundtrip(self):
        """Windows 名解析正确，且传给 Graph 的名字保持 Windows 官方名。"""
        zi, gname = _mk_tz("US Mountain Standard Time")
        assert gname == "US Mountain Standard Time"
        assert zi.key == "America/Phoenix"  # 亚利桑那：UTC-7 无夏令时

    def test_iana_name_is_preserved(self):
        """IANA 名必须保留，避免多对一 Windows 映射改变地区规则。"""
        zi, gname = _mk_tz("Asia/Hong_Kong")
        assert gname == "Asia/Hong_Kong"
        assert zi == _resolve_tz("Asia/Hong_Kong")

    def test_unknown_returns_none(self):
        """解析不了返回 None，交给探测链的下一级。"""
        assert _mk_tz("Mars/Phobos") is None
        assert _mk_tz("") is None


class TestExplicitTimezone:
    """显式输入的时区必须有效，不能警告后静默回退或改变地区规则。"""

    @pytest.mark.parametrize("name,iana", [
        ("China Standard Time", "Asia/Shanghai"),
        ("Eastern Standard Time", "America/New_York"),
        ("UTC", None),
        ("GMT", None),
        ("Etc/UTC", None),
        ("Etc/GMT", None),
        ("Asia/Shanghai", "Asia/Shanghai"),
        ("Asia/Urumqi", "Asia/Urumqi"),
        ("America/New_York", "America/New_York"),
    ])
    def test_named_timezones(self, name, iana):
        graph_name, tz = resolve_timezone(name)
        assert graph_name == name
        assert getattr(tz, "key", None) == iana

    def test_iana_region_is_not_replaced_with_different_windows_rules(self):
        graph_name, tz = resolve_timezone("Asia/Urumqi")
        assert graph_name == "Asia/Urumqi"
        assert datetime(2026, 8, 10, tzinfo=tz).utcoffset().total_seconds() == 6 * 3600

    @pytest.mark.parametrize("name", [
        "", None, 123, "Mars/Phobos", "UTC+8", "CST-8", "Z",
        " Asia/Shanghai", "Asia/Shanghai ", "../Asia/Shanghai", "/Asia/Shanghai",
    ])
    def test_invalid_timezone_fails_without_warning_or_fallback(self, name, capsys):
        with pytest.raises(CalError):
            resolve_timezone(name)
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""

    def test_missing_timezone_database_fails(self, monkeypatch):
        monkeypatch.setattr("ocal_time.ZoneInfo", None)
        with pytest.raises(CalError):
            resolve_timezone("China Standard Time")

    @pytest.mark.parametrize("name", ["UTC", "GMT", "Etc/UTC", "Etc/GMT"])
    @pytest.mark.parametrize("has_zoneinfo", [True, False])
    def test_fixed_utc_names_need_no_timezone_database(self, monkeypatch, name, has_zoneinfo):
        def missing_database(key):
            pytest.fail("UTC must not query an external timezone database")

        monkeypatch.setattr("ocal_time.ZoneInfo", missing_database if has_zoneinfo else None)
        graph_name, tz = resolve_timezone(name)
        assert graph_name == name
        for month in (1, 7):
            assert datetime(2026, month, 15, tzinfo=tz).utcoffset().total_seconds() == 0

    def test_resolution_does_not_change_module_timezone(self):
        import ocal_time
        original = ocal_time.LOCAL_TZ, ocal_time.LOCAL_TZ_NAME
        resolve_timezone("America/New_York")
        assert (ocal_time.LOCAL_TZ, ocal_time.LOCAL_TZ_NAME) == original


class TestTzFromEnv:
    """TZ 环境变量探测 _tz_from_env（探测链第一优先级）。"""

    def test_iana_name(self, monkeypatch):
        """TZ=IANA 名直接可用。"""
        monkeypatch.setenv("TZ", "Asia/Shanghai")
        zi, gname = _tz_from_env()
        assert gname == "Asia/Shanghai"
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

    @pytest.mark.parametrize("value", ["EST5EDT", "CST6CDT", "Hongkong"])
    def test_legacy_iana_alias_is_preserved(self, monkeypatch, value):
        """An available tzdata backward link retains its exact timezone rules."""
        monkeypatch.setenv("TZ", value)
        zi, gname = _tz_from_env()
        assert gname == value
        assert zi == _resolve_tz(value)

    def test_unset(self, monkeypatch):
        """没设 TZ 返回 None，交给下一级探测。"""
        monkeypatch.delenv("TZ", raising=False)
        assert _tz_from_env() is None

    @pytest.mark.parametrize("name, winter_hours, summer_hours", [
        ("Asia/Urumqi", 6, 6),
        ("America/New_York", -5, -4),
        ("America/Chihuahua", -6, -6),
        ("Australia/Lord_Howe", 11, 10.5),
        ("China Standard Time", 8, 8),
        ("Eastern Standard Time", -5, -4),
    ])
    def test_context_timezone_roundtrip_preserves_offset_and_dst(self, monkeypatch, capsys,
                                                               name, winter_hours, summer_hours):
        """Reusing the timezone reported by context must not change dates or DST rules."""
        import json
        from types import SimpleNamespace
        import ocal_time
        import ocal_context

        monkeypatch.setenv("TZ", name)
        detected_tz, detected_name = ocal_time._detect_local_tz()
        monkeypatch.setattr(ocal_time, "LOCAL_TZ", detected_tz)
        monkeypatch.setattr(ocal_time, "LOCAL_TZ_NAME", detected_name)
        assert ocal_context.cmd_context(SimpleNamespace(json=True)) == 0
        context = json.loads(capsys.readouterr().out)
        reused_name, reused_tz = resolve_timezone(context["timezone"])
        assert detected_name == reused_name == name
        for month, expected_hours in ((1, winter_hours), (7, summer_hours)):
            instant = datetime(2026, month, 15, 12)
            detected = instant.replace(tzinfo=detected_tz)
            reused = instant.replace(tzinfo=reused_tz)
            assert detected.isoformat() == reused.isoformat()
            assert detected.utcoffset().total_seconds() == expected_hours * 3600
            assert detected.dst() == reused.dst()


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


@pytest.mark.parametrize("posix", [False, True])
def test_final_fallback_clock_agrees_with_utc_name(monkeypatch, capsys, posix):
    import ocal_time
    from types import SimpleNamespace
    from datetime import timedelta
    local = timezone(timedelta(hours=5, minutes=30))
    monkeypatch.setattr(ocal_time, "datetime", SimpleNamespace(now=lambda: SimpleNamespace(
        astimezone=lambda: SimpleNamespace(tzinfo=local))))
    monkeypatch.setattr(ocal_time, "_tz_from_env", lambda: _POSIX_TZ if posix else None)
    for name in ("_tz_from_winreg", "_tz_from_system_tzinfo", "_tz_from_etc_timezone",
                 "_tz_from_localtime_link", "_tz_from_localtime_content", "_tz_from_offset"):
        monkeypatch.setattr(ocal_time, name, lambda: None)
    tzinfo, name = ocal_time._detect_local_tz()
    assert name == "UTC" and tzinfo == timezone.utc
    assert capsys.readouterr().err


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
