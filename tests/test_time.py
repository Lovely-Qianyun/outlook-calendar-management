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
    _resolve_tz, _fmt, _weekday,
)


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
