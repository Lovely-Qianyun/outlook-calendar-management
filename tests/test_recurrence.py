"""Structured recurrence input, human output, numbering and range validation."""
import json
from datetime import datetime

import pytest

from ocal_errors import CalError
from ocal_i18n import set_lang
from ocal_recurrence import _parse_recurrence, _fmt_recurrence, _occurrence_number, _build_recurrence

START = datetime(2026, 8, 7)  # 周五
DAILY = '{"type":"daily","interval":1}'
WEEKLY = {"type": "weekly", "interval": 1, "daysOfWeek": ["friday"], "firstDayOfWeek": "monday"}


class TestParseRecurrence:
    @pytest.mark.parametrize("pattern", [
        {"type": "daily", "interval": 1},
        {"type": "daily", "interval": 3},
        WEEKLY,
        {**WEEKLY, "interval": 2, "daysOfWeek": ["monday", "wednesday"]},
        {**WEEKLY, "daysOfWeek": ["monday", "tuesday", "wednesday", "thursday", "friday"]},
        {"type": "absoluteMonthly", "interval": 3, "dayOfMonth": 31},
        {"type": "relativeMonthly", "interval": 2, "index": "last", "daysOfWeek": ["friday"]},
        {"type": "relativeMonthly", "interval": 1, "index": "second", "daysOfWeek": ["thursday", "friday"]},
        {"type": "absoluteYearly", "interval": 1, "month": 9, "dayOfMonth": 21},
        {"type": "absoluteYearly", "interval": 4, "month": 2, "dayOfMonth": 29},
        {"type": "relativeYearly", "interval": 2, "month": 11, "index": "last", "daysOfWeek": ["wednesday"]},
    ])
    def test_valid_patterns_preserved(self, pattern):
        rec, description = _parse_recurrence(json.dumps(pattern), START)
        assert rec["pattern"] == pattern
        assert rec["range"] == {"type": "noEnd", "startDate": "2026-08-07"}
        assert isinstance(description, str) and description

    @pytest.mark.parametrize("bad", [
        "每天", "工作日", "每周五", "每月15日", "daily", "every friday", "weekly",
        "", "null", "[]", "123", '"daily"', '{"type":"daily",',
        {"type": "daily", "interval": 1}, None,
    ])
    def test_non_json_patterns_rejected_with_actionable_error(self, bad):
        with pytest.raises(CalError, match="--repeat-file"):
            _parse_recurrence(bad, START)

    @pytest.mark.parametrize("pattern,field", [
        ({}, "type"),
        ({"type": ["daily"], "interval": 1}, "type"),
        ({"type": "hourly", "interval": 1}, "type"),
        ({"type": "daily"}, "interval"),
        ({"type": "daily", "interval": 1, "timezone": "UTC"}, "timezone"),
        ({"type": "daily", "interval": 1, "daysOfWeek": ["monday"]}, "daysOfWeek"),
        ({"pattern": {"type": "daily", "interval": 1}}, "type"),
        ({"type": "weekly", "interval": 1, "firstDayOfWeek": "monday"}, "daysOfWeek"),
        ({"type": "weekly", "interval": 1, "daysOfWeek": ["monday"]}, "firstDayOfWeek"),
        ({**WEEKLY, "firstDayOfWeek": "Monday"}, "firstDayOfWeek"),
        ({**WEEKLY, "firstDayOfWeek": []}, "firstDayOfWeek"),
        ({**WEEKLY, "daysOfWeek": []}, "daysOfWeek"),
        ({**WEEKLY, "daysOfWeek": "friday"}, "daysOfWeek"),
        ({**WEEKLY, "daysOfWeek": ["Friday"]}, "daysOfWeek"),
        ({**WEEKLY, "daysOfWeek": ["friday", "friday"]}, "duplicates"),
        ({**WEEKLY, "daysOfWeek": [1]}, "daysOfWeek"),
        ({**WEEKLY, "daysOfWeek": [["friday"]]}, "daysOfWeek"),
        ({"type": "relativeMonthly", "interval": 1, "daysOfWeek": ["monday"]}, "index"),
        ({"type": "relativeMonthly", "interval": 1, "index": "fifth", "daysOfWeek": ["monday"]}, "index"),
        ({"type": "relativeYearly", "interval": 1, "index": "first", "daysOfWeek": ["monday"]}, "month"),
        ({"type": "absoluteYearly", "interval": 1, "month": 2, "dayOfMonth": 30}, "calendar date"),
        ({"type": "absoluteYearly", "interval": 1, "month": 4, "dayOfMonth": 31}, "calendar date"),
    ])
    def test_invalid_shapes_rejected(self, pattern, field):
        with pytest.raises(CalError, match=field):
            _parse_recurrence(json.dumps(pattern), START)

    @pytest.mark.parametrize("field,value", [
        ("interval", 0), ("interval", -1), ("interval", True), ("interval", 1.0),
        ("interval", "1"), ("interval", 2_147_483_648), ("interval", None),
        ("month", 0), ("month", 13), ("month", False), ("month", 1.5),
        ("dayOfMonth", 0), ("dayOfMonth", 32), ("dayOfMonth", True),
    ])
    def test_integer_fields_are_strict(self, field, value):
        pattern = {"type": "absoluteYearly", "interval": 1, "month": 9, "dayOfMonth": 21}
        pattern[field] = value
        with pytest.raises(CalError, match=field):
            _parse_recurrence(json.dumps(pattern), START)

    @pytest.mark.parametrize("raw", [
        '{"type":"daily","interval":2,"interval":1}',
        '{"type":"daily","type":"weekly","interval":1}',
    ])
    def test_duplicate_keys_are_never_silently_overwritten(self, raw):
        with pytest.raises(CalError, match="duplicate field"):
            _parse_recurrence(raw, START)

    def test_weekday_is_not_inferred_from_start(self):
        rec, _ = _parse_recurrence(json.dumps({**WEEKLY, "daysOfWeek": ["monday"]}), START)
        assert START.weekday() == 4
        assert rec["pattern"]["daysOfWeek"] == ["monday"]


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
        ({"type": "absoluteMonthly", "interval": 3, "dayOfMonth": 15},
         "每3个月15日", "Every 3 months on day 15"),
        ({"type": "relativeMonthly", "interval": 1, "index": "last", "daysOfWeek": ["friday"]},
         "每月最后一个周五", "Monthly on the last Friday"),
        ({"type": "relativeMonthly", "interval": 2, "index": "last", "daysOfWeek": ["friday"]},
         "每2个月最后一个周五", "Every 2 months on the last Friday"),
        ({"type": "absoluteYearly", "interval": 1, "month": 9, "dayOfMonth": 21},
         "每年9月21日", "Yearly on 9/21"),
        ({"type": "absoluteYearly", "interval": 2, "month": 9, "dayOfMonth": 21},
         "每2年9月21日", "Every 2 years on 9/21"),
        ({"type": "relativeYearly", "interval": 1, "month": 11, "index": "last", "daysOfWeek": ["wednesday"]},
         "每年11月最后一个周三", "Yearly in month 11 on the last Wednesday"),
        ({"type": "relativeYearly", "interval": 2, "month": 11, "index": "last", "daysOfWeek": ["wednesday"]},
         "每2年11月最后一个周三", "Every 2 years in month 11 on the last Wednesday"),
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

    def test_relative_weekday_candidates_are_all_visible(self):
        rec = self._rec({"type": "relativeMonthly", "interval": 1,
                         "index": "second", "daysOfWeek": ["thursday", "friday"]})
        set_lang("zh")
        assert _fmt_recurrence(rec) == "每月第二个周四+周五（多个星期候选中最早匹配的日期）"
        set_lang("en")
        assert _fmt_recurrence(rec) == "Monthly on the second Thursday, Friday (the first matching date among these weekdays)"

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
        """Month/year series are expanded by Graph; do not guess an ordinal."""
        rec = self._rec({"type": "absoluteMonthly", "interval": 1, "dayOfMonth": 15})
        assert _occurrence_number(rec, "2026-10-15T09:00:00") is None

    def test_yearly(self):
        """Yearly rules can skip dates such as February 29."""
        rec = self._rec({"type": "absoluteYearly", "interval": 1, "month": 9, "dayOfMonth": 21})
        assert _occurrence_number(rec, "2028-09-21T09:00:00") is None

    def test_daily_only_counts_matching_dates(self):
        rec = self._rec({"type": "daily", "interval": 3})
        assert _occurrence_number(rec, "2026-08-07T09:00:00") == 3
        assert _occurrence_number(rec, "2026-08-08T09:00:00") is None

    def test_multiple_week_intervals_are_not_estimated(self):
        # Range starts on Saturday; Sunday-based week buckets differ from start+7.
        rec = self._rec({"type": "weekly", "interval": 2,
                         "daysOfWeek": ["monday"], "firstDayOfWeek": "sunday"})
        assert _occurrence_number(rec, "2026-08-03T09:00:00") is None

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
    """The JSON pattern is combined with one explicit range ending."""

    def test_without_end(self):
        from ocal_time import LOCAL_TZ_NAME
        rec, _ = _build_recurrence(DAILY, None, None, START)
        assert rec["range"] == {
            "type": "noEnd", "startDate": "2026-08-07", "recurrenceTimeZone": LOCAL_TZ_NAME,
        }

    def test_with_until(self):
        """带截止日期：range 变成 endDate 并带上日期。"""
        rec, desc = _build_recurrence(DAILY, "2026-12-31", None, START)
        assert rec["range"]["type"] == "endDate"
        assert rec["range"]["endDate"] == "2026-12-31"
        assert desc

    def test_with_times(self):
        """带总次数：range 变成 numbered 并带上次数。"""
        rec, desc = _build_recurrence(DAILY, None, 5, START)
        assert rec["range"]["type"] == "numbered"
        assert rec["range"]["numberOfOccurrences"] == 5
        assert "5" in desc

    def test_unparseable_raises(self):
        """Natural-language recurrence is no longer accepted."""
        with pytest.raises(CalError):
            _build_recurrence("每3小时", None, None, START)

    @pytest.mark.parametrize("until", ["2026/12/31", "2026-9-30", "2026-09-8", "2026-02-30", "明天", "2026-12-31T00:00", 20261231])
    def test_bad_until_format_raises(self, until):
        """截止日期不是 YYYY-MM-DD 要报错。"""
        with pytest.raises(CalError):
            _build_recurrence(DAILY, until, None, START)

    def test_until_before_start_raises(self):
        """截止早于开始日期没有意义，要报错。"""
        with pytest.raises(CalError):
            _build_recurrence(DAILY, "2026-01-01", None, START)

    @pytest.mark.parametrize("n", [0, -1, True, 1.0, "5", 2_147_483_648])
    def test_invalid_count_raises(self, n):
        """次数为 0 或负数要报错。"""
        with pytest.raises(CalError):
            _build_recurrence(DAILY, None, n, START)

    def test_conflicting_end_options_rejected(self):
        with pytest.raises(CalError, match="--repeat-until"):
            _build_recurrence(DAILY, "2026-12-31", 5, START)

    def test_end_may_equal_start_date(self):
        rec, _ = _build_recurrence(DAILY, "2026-08-07", None, START)
        assert rec["range"]["endDate"] == rec["range"]["startDate"]

    def test_date_object_from_update_is_supported(self):
        rec, _ = _build_recurrence(DAILY, "2026-08-10", None, START.date())
        assert rec["range"]["startDate"] == "2026-08-07"
        assert rec["range"]["endDate"] == "2026-08-10"
