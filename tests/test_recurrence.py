"""ocal_recurrence 的测试。

被测模块负责定期规则的全部文字工作：
- _parse_recurrence 把自然语言规则（每周五、monthly on day 15）解析成 Graph 的 recurrence 对象
- _fmt_recurrence 把 Graph 对象翻译回人话，list/read 显示用
- _occurrence_number 数出某个出现是系列的第几次
- _build_recurrence 在解析基础上套结束条件（次数/截止日），add/update 共用

规则写法多、中英文都有，是本项目最容易写错也最容易改坏的部分。
测试按两条主线组织：合法规则全部能解析、非法规则全部被拒绝。
"""
from datetime import datetime

import pytest

from ocal_errors import CalError
from ocal_i18n import set_lang
from ocal_recurrence import _parse_recurrence, _fmt_recurrence, _occurrence_number, _build_recurrence

START = datetime(2026, 8, 7)  # 周五


class TestParseRecurrence:
    """规则解析 _parse_recurrence。

    覆盖每天/每N天/工作日/每周X/每N周X/每月N日/每月第N个周X/每年X月X日，
    中英文写法都要能解析；解析产物必须带正确的 pattern 和 range。
    """

    @pytest.mark.parametrize("desc,type_,interval,days", [
        ("每天", "daily", 1, None),
        ("每日", "daily", 1, None),
        ("每3天", "daily", 3, None),
        ("daily", "daily", 1, None),
        ("every day", "daily", 1, None),
        ("every 3 days", "daily", 3, None),
        ("工作日", "weekly", 1, ["monday", "tuesday", "wednesday", "thursday", "friday"]),
        ("weekdays", "weekly", 1, ["monday", "tuesday", "wednesday", "thursday", "friday"]),
        ("每周", "weekly", 1, ["friday"]),          # 缺日默认从起始日（周五）算
        ("每周一+三", "weekly", 1, ["monday", "wednesday"]),
        ("每2周周三", "weekly", 2, ["wednesday"]),
        ("weekly", "weekly", 1, ["friday"]),
        ("every friday", "weekly", 1, ["friday"]),
        ("每月15日", "absoluteMonthly", 1, None),
        ("monthly on day 15", "absoluteMonthly", 1, None),
        ("每年9月21日", "absoluteYearly", 1, None),
        ("yearly on 9/21", "absoluteYearly", 1, None),
    ])
    def test_valid_rules_parse(self, desc, type_, interval, days):
        """中英文全部合法写法逐一解析，校验 pattern 的类型/间隔/星期。

        同时校验 range.startDate 取的是开始日期，以及返回的人类可读描述非空。
        """
        rec, desc_str = _parse_recurrence(desc, START)
        assert rec is not None, desc
        assert rec["pattern"]["type"] == type_, desc
        assert rec["pattern"]["interval"] == interval, desc
        assert rec["pattern"].get("daysOfWeek") == days, desc
        assert rec["range"]["startDate"] == "2026-08-07"
        assert isinstance(desc_str, str) and desc_str

    @pytest.mark.parametrize("bad", [
        "每0天", "每0周", "每月32日", "每月0日", "每月第5个周三", "每年13月1日",
        "每3小时", "每N个工作日", "完全看不懂", "",
    ])
    def test_invalid_rules_return_none(self, bad):
        """非法规则统一返回 (None, None)。

        覆盖间隔为 0、日期越界（32 日/0 日）、第 5 个周几、13 月、
        不支持的类型（每3小时）、完全乱写、空串。
        解析不出来的规则由 _build_recurrence 转成友好报错，
        绝不能悄悄创建错误的系列。
        """
        assert _parse_recurrence(bad, START) == (None, None)

    def test_relative_monthly_structure(self):
        """每月第 N 个周几：校验 index（first/last）和星期字段。

        Graph 用 relativeMonthly + index + daysOfWeek 表达这类规则，
        结构错了后面格式化、计数全都会错。
        """
        rec, _ = _parse_recurrence("每月最后一个周五", START)
        assert rec["pattern"]["type"] == "relativeMonthly"
        assert rec["pattern"]["index"] == "last"
        assert rec["pattern"]["daysOfWeek"] == ["friday"]


class TestFmtRecurrence:
    """规则格式化 _fmt_recurrence。

    把 Graph 的 recurrence 对象翻译成人类可读描述，read/list 显示用。
    两种语言各有一套文案，中文还要照顾"最后一个周五"这种特有表达
    （模板拼出来是"最后个"，需要修正成"最后一个"）。
    """

    def _rec(self, pattern, range_=None):
        """构造带 pattern 的 recurrence 对象，range 可覆盖。"""
        rec = {"pattern": pattern, "range": range_ or {"type": "noEnd"}}
        return rec

    @pytest.mark.parametrize("pattern,zh,en", [
        ({"type": "daily", "interval": 1}, "每天", "Daily"),
        ({"type": "daily", "interval": 3}, "每3天", "Every 3 days"),
        ({"type": "weekly", "interval": 1,
          "daysOfWeek": ["monday", "tuesday", "wednesday", "thursday", "friday"]},
         "每个工作日", "Every weekday"),
        ({"type": "weekly", "interval": 1, "daysOfWeek": ["monday", "wednesday"]},
         "每周周一+周三", "Weekly on Monday, Wednesday"),
        ({"type": "weekly", "interval": 2, "daysOfWeek": ["wednesday"]},
         "每2周周三", "Every 2 weeks on Wednesday"),
        ({"type": "absoluteMonthly", "interval": 1, "dayOfMonth": 15},
         "每月15日", "Monthly on day 15"),
        ({"type": "relativeMonthly", "interval": 1, "index": "last", "daysOfWeek": ["friday"]},
         "每月最后一个周五", "Monthly on the last Friday"),
        ({"type": "absoluteYearly", "interval": 1, "month": 9, "dayOfMonth": 21},
         "每年9月21日", "Yearly on 9/21"),
    ])
    def test_all_types_both_languages(self, pattern, zh, en):
        """每种规则类型在 zh/en 下的完整描述逐字比对。

        描述是直接给用户看的，逐字比对能防止翻译表改坏。
        """
        rec = self._rec(pattern)
        set_lang("zh")
        assert _fmt_recurrence(rec) == zh
        set_lang("en")
        assert _fmt_recurrence(rec) == en

    def test_empty_returns_empty(self):
        """空对象返回空串，显示层不用特判空 recurrence。"""
        assert _fmt_recurrence(None) == ""
        assert _fmt_recurrence({}) == ""

    @pytest.mark.parametrize("range_,zh_tail,en_tail", [
        ({"type": "numbered", "numberOfOccurrences": 5}, "（共5次）", " (5 occurrences)"),
        ({"type": "endDate", "endDate": "2026-12-31"}, "（至2026-12-31）", " (until 2026-12-31)"),
    ])
    def test_range_suffixes(self, range_, zh_tail, en_tail):
        """结束条件后缀（共 N 次 / 至某日），两种语言都要对。"""
        rec = self._rec({"type": "daily", "interval": 1}, range_)
        set_lang("zh")
        assert _fmt_recurrence(rec).endswith(zh_tail)
        set_lang("en")
        assert _fmt_recurrence(rec).endswith(en_tail)

    def test_unknown_type_passthrough(self):
        """不认识的类型原样返回类型名，别编造描述。

        Graph 未来可能加新类型，宁可显示原始类型名也不能乱翻译。
        """
        rec = self._rec({"type": "hourly", "interval": 1})
        assert _fmt_recurrence(rec) == "hourly"


class TestOccurrenceNumber:
    """第 N 次出现计算 _occurrence_number。

    read 里"这是该系列的第 N 次出现"靠它。按周期从 range.startDate 数过去，
    不调 /instances 端点——省一次请求，也躲开它的分页问题。
    算不出来返回 None 而不是抛错，显示层按"不显示"处理。
    """

    def _rec(self, pattern):
        """构造以 2026-08-01 为开始的 recurrence 对象。"""
        return {"pattern": pattern, "range": {"startDate": "2026-08-01", "type": "noEnd"}}

    def test_daily(self):
        """每天一次：按天数差计数，08-03 是第 3 次。"""
        rec = self._rec({"type": "daily", "interval": 1})
        assert _occurrence_number(rec, "2026-08-03T09:00:00") == 3

    def test_weekly(self):
        """每周一：数到第三个周一（08-17）就是第 3 次。"""
        rec = self._rec({"type": "weekly", "interval": 1, "daysOfWeek": ["monday"]})
        assert _occurrence_number(rec, "2026-08-17T09:00:00") == 3

    def test_monthly(self):
        """每月一次：按月份差计数，跨年也对（10 月 - 8 月 = 2，即第 3 次）。"""
        rec = self._rec({"type": "absoluteMonthly", "interval": 1, "dayOfMonth": 15})
        assert _occurrence_number(rec, "2026-10-15T09:00:00") == 3

    def test_yearly(self):
        """每年一次：按年份差计数。"""
        rec = self._rec({"type": "absoluteYearly", "interval": 1, "month": 9, "dayOfMonth": 21})
        assert _occurrence_number(rec, "2028-09-21T09:00:00") == 3

    def test_before_start_returns_none(self):
        """早于系列开始日期不算次数，返回 None。"""
        rec = self._rec({"type": "daily", "interval": 1})
        assert _occurrence_number(rec, "2026-07-31T09:00:00") is None

    @pytest.mark.parametrize("rec,occ", [
        (None, "2026-08-03T09:00:00"),
        ({"pattern": {}, "range": {}}, "2026-08-03T09:00:00"),
        ({"pattern": {"type": "daily", "interval": 1}, "range": {"startDate": "2026-08-01"}}, "垃圾"),
    ])
    def test_uncomputable_returns_none(self, rec, occ):
        """数据不完整或格式坏时返回 None，不抛异常。"""
        assert _occurrence_number(rec, occ) is None


class TestBuildRecurrence:
    """规则构造 _build_recurrence：解析 + 结束条件。

    add/update 的 --repeat 都走这里。规则看不懂、截止日期格式错、
    截止早于开始、次数为 0 或负数，都要抛 CalError 给友好提示。
    """

    def test_with_until(self):
        """带截止日期：range 变成 endDate 并带上日期。"""
        rec, desc = _build_recurrence("每天", "2026-12-31", None, START)
        assert rec["range"]["type"] == "endDate"
        assert rec["range"]["endDate"] == "2026-12-31"
        assert desc

    def test_with_times(self):
        """带总次数：range 变成 numbered 并带上次数。"""
        rec, _ = _build_recurrence("每天", None, 5, START)
        assert rec["range"]["type"] == "numbered"
        assert rec["range"]["numberOfOccurrences"] == 5

    def test_unparseable_raises(self):
        """规则看不懂要报错，报错文案里会附上支持的写法列表。"""
        with pytest.raises(CalError):
            _build_recurrence("每3小时", None, None, START)

    def test_bad_until_format_raises(self):
        """截止日期不是 YYYY-MM-DD 要报错。"""
        with pytest.raises(CalError):
            _build_recurrence("每天", "2026/12/31", None, START)

    def test_until_before_start_raises(self):
        """截止早于开始日期没有意义，要报错。"""
        with pytest.raises(CalError):
            _build_recurrence("每天", "2026-01-01", None, START)

    @pytest.mark.parametrize("n", [0, -1])
    def test_invalid_count_raises(self, n):
        """次数为 0 或负数要报错。"""
        with pytest.raises(CalError):
            _build_recurrence("每天", None, n, START)
