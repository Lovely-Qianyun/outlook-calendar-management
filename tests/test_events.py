"""ocal_events 的测试。

被测模块是命令实现层，两类内容：
- 纯函数：重叠判断、筛选、空闲计算、显示格式化，不碰网络
- 命令路径：add/update/delete/read/list，用 mock 把 get_token/_call/_get_all
  换成假的，离线验证参数组装、输出文案和错误处理

测试数据用 _event() 构造最小 Graph 事件 dict，mock 掉网络后命令
可以在任何机器上跑，不需要真实账户。命令的输出走了 i18n，
涉及中文/英文文案的用例会先 set_lang 再断言。
"""
import json
from datetime import datetime, date
from types import SimpleNamespace

import pytest

import ocal_events as ev
from ocal_errors import CalError
from ocal_i18n import set_lang


def _args(**kw):
    """构造 argparse 风格参数对象。

    命令从 args 上取字段，这里把缺省值补全（json=False 等），
    测试里只覆盖自己要关心的字段。
    """
    defaults = dict(json=False)
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _event(**over):
    """构造最小 Graph 事件 dict。

    字段按 Graph 实际返回的结构造（start/end 带 dateTime 和 timeZone），
    测试里用关键字参数覆盖个别字段，比如 _event(subject="新标题")。
    """
    base = {
        "id": "E1",
        "subject": "测试日程",
        "start": {"dateTime": "2026-08-10T09:00:00", "timeZone": "China Standard Time"},
        "end": {"dateTime": "2026-08-10T10:00:00", "timeZone": "China Standard Time"},
        "location": {"displayName": "3号会议室"},
        "categories": ["工作"],
        "isAllDay": False,
        "recurrence": None,
        "seriesMasterId": None,
        "type": "singleInstance",
        "isCancelled": False,
        "bodyPreview": "讨论Q3计划",
        "showAs": "busy",
    }
    base.update(over)
    return base


def _mock_net(monkeypatch, call_fn=None, get_all=None):
    """mock 掉认证与网络层，让命令离线可跑。

    get_token 恒返回 "tk"，_call 和 _get_all 按测试需要注入假实现，
    不注入时 _call 默认返回 _event()、_get_all 默认返回空列表。
    """
    monkeypatch.setattr(ev, "get_token", lambda: "tk")
    monkeypatch.setattr(ev, "_call", call_fn or (lambda *a, **k: _event()))
    monkeypatch.setattr(ev, "_get_all", get_all or (lambda *a, **k: []))


class TestOverlaps:
    """重叠判断 _overlaps。

    冲突检测和空闲计算的地基。五个边界情形必须全部正确：
    不相交、首尾相接（不算重叠）、相交、包含、完全相同。
    """

    @pytest.mark.parametrize("a,b,expect", [
        ((9, 10), (11, 12), False),   # 不相交
        ((9, 10), (10, 11), False),   # 首尾相接不算
        ((9, 11), (10, 12), True),    # 相交
        ((9, 12), (10, 11), True),    # 包含
        ((9, 10), (9, 10), True),     # 完全相同
    ])
    def test_cases(self, a, b, expect):
        """重叠判断的各种边界情形。

        注意"首尾相接不算重叠"是刻意设计：前一个 10:00 结束、
        后一个 10:00 开始，不构成冲突。
        """
        assert ev._overlaps(*a, *b) is expect


class TestFilterEvents:
    """本地筛选 _filter_events。

    list 的 --search / --category 在 Graph 数据拉回之后本地过滤。
    关键词匹配标题/地点/备注，不区分大小写；类别按包含判断。
    """

    def _events(self):
        """构造三组不同特征的测试事件。"""
        return [
            _event(id="1", subject="周会讨论", location={"displayName": "3号会议室"},
                   bodyPreview="议题A", categories=["工作"]),
            _event(id="2", subject="Meeting Q3", location={"displayName": "线上"},
                   bodyPreview="预算", categories=["重要"]),
            _event(id="3", subject="生日", location={"displayName": ""},
                   bodyPreview="", categories=["私人"]),
        ]

    def test_by_subject(self):
        """按标题关键词过滤。"""
        assert [e["id"] for e in ev._filter_events(self._events(), search="周会")] == ["1"]

    def test_by_location(self):
        """按地点过滤，地点来自 location.displayName。"""
        assert [e["id"] for e in ev._filter_events(self._events(), search="会议室")] == ["1"]

    def test_by_body(self):
        """按备注过滤，备注来自 bodyPreview。"""
        assert [e["id"] for e in ev._filter_events(self._events(), search="预算")] == ["2"]

    def test_search_case_insensitive(self):
        """英文关键词不区分大小写，meeting 能匹配 Meeting。"""
        assert [e["id"] for e in ev._filter_events(self._events(), search="meeting")] == ["2"]

    def test_by_category(self):
        """按类别过滤，事件的 categories 列表包含即算。"""
        assert [e["id"] for e in ev._filter_events(self._events(), category="重要")] == ["2"]

    def test_no_match(self):
        """没有任何匹配时返回空列表，不会报错。"""
        assert ev._filter_events(self._events(), search="不存在") == []

    def test_no_filter_returns_all(self):
        """搜索和类别都没给时原样返回，顺序不变。"""
        events = self._events()
        assert ev._filter_events(events) == events


class TestParseImportance:
    """重要度归一 _parse_importance。

    用户可能输中文（高）也可能输英文（high），统一映射成
    Graph 的 low/normal/high；其余值原样返回，交给 argparse 的 choices 兜底。
    """

    @pytest.mark.parametrize("v,expect", [("低", "low"), ("普通", "normal"), ("高", "high"),
                                          ("high", "high"), ("乱值", "乱值")])
    def test_mapping(self, v, expect):
        """中文和英文重要度都归一成 Graph 的值。"""
        assert ev._parse_importance(v) == expect


class TestEventDateStr:
    """事件所在日历日 _event_date_str。

    list 按天分组的键：全天事件按日期段算（end 是次日零点，取前一天），
    时段事件按开始时间算，跟随当前语言。
    """

    def test_all_day(self):
        """全天事件：start 08-10、end 08-11，落在 08-10。"""
        e = _event(isAllDay=True,
                   start={"dateTime": "2026-08-10T00:00:00", "timeZone": "China Standard Time"},
                   end={"dateTime": "2026-08-11T00:00:00", "timeZone": "China Standard Time"})
        assert ev._event_date_str(e) == "08月10日 周一"

    def test_timed(self):
        """时段事件：按开始时间算日历日。"""
        assert ev._event_date_str(_event()) == "08月10日 周一"

    def test_english(self):
        """英文环境用英文日期和星期。"""
        set_lang("en")
        assert ev._event_date_str(_event()) == "08/10 Mon"


class TestPrintEvents:
    """列表打印 _print_events。

    list/today/next 共用的显示逻辑。这里盯一个协议级要求：
    每一行必须带 🆔 锚点——agent 从它提取事件 ID，漏了输出协议就断了。
    """

    def test_empty_list_hint(self, capsys):
        """空列表给出提示而不是报错。"""
        ev._print_events([], "标题")
        assert "没有符合条件的日程" in capsys.readouterr().out

    def test_id_anchor_per_line(self, capsys):
        """每行都带 🆔 锚点，这是输出协议的一部分。"""
        ev._print_events([_event()], "标题")
        out = capsys.readouterr().out
        assert "测试日程" in out
        assert "🆔 E1" in out

    def test_summary_mode(self, capsys):
        """摘要模式只给条数，不显示明细和 ID。"""
        ev._print_events([_event(), _event(id="E2")], "标题", summary=True)
        out = capsys.readouterr().out
        assert "2 条" in out
        assert "🆔" not in out


class TestComputeFreeSlots:
    """空闲时段计算 _compute_free_slots。

    free 命令的本地算法，规则：
    - showAs=free 的日程不算占用
    - 全天事件占整天，时段事件按实际起止
    - 跨出查询窗口的部分只算窗口内
    - 首尾相接的占用合并成一段，空闲段取其补集
    """

    def _day(self):
        """测试用的固定日期。"""
        return date(2026, 8, 10)

    def _slot(self, start, end):
        """把 (时, 分) 转成当天 10 号的 naive datetime。"""
        return datetime(2026, 8, 10, *start), datetime(2026, 8, 10, *end)

    def test_no_events_all_free(self):
        """没有事件时整个窗口都是空闲。"""
        free = ev._compute_free_slots([], self._day(), 9 * 60, 18 * 60)
        assert free == [self._slot((9, 0), (18, 0))]

    def test_full_busy_no_free(self):
        """占用盖满窗口时没有空闲。"""
        events = [_event(id="1", start={"dateTime": "2026-08-10T08:00:00", "timeZone": "China Standard Time"},
                         end={"dateTime": "2026-08-10T20:00:00", "timeZone": "China Standard Time"})]
        assert ev._compute_free_slots(events, self._day(), 9 * 60, 18 * 60) == []

    def test_free_showas_ignored(self):
        """showAs=free 的日程不算占用，窗口保持全空闲。"""
        events = [_event(id="1", showAs="free")]
        free = ev._compute_free_slots(events, self._day(), 9 * 60, 18 * 60)
        assert free == [self._slot((9, 0), (18, 0))]

    def test_adjacent_busy_merged(self):
        """首尾相接的占用合并成一段，空闲段随之合并。"""
        events = [
            _event(id="1", start={"dateTime": "2026-08-10T09:30:00", "timeZone": "China Standard Time"},
                   end={"dateTime": "2026-08-10T10:00:00", "timeZone": "China Standard Time"}),
            _event(id="2", start={"dateTime": "2026-08-10T10:00:00", "timeZone": "China Standard Time"},
                   end={"dateTime": "2026-08-10T11:00:00", "timeZone": "China Standard Time"}),
        ]
        free = ev._compute_free_slots(events, self._day(), 9 * 60, 18 * 60)
        assert free == [self._slot((9, 0), (9, 30)), self._slot((11, 0), (18, 0))]

    def test_clipped_to_window(self):
        """跨出窗口的占用只算窗口内的部分。

        事件 08:00-20:00 但窗口是 09:00-18:00，窗口内全被占，没有空闲。
        """
        events = [_event(id="1", start={"dateTime": "2026-08-10T08:00:00", "timeZone": "China Standard Time"},
                         end={"dateTime": "2026-08-10T20:00:00", "timeZone": "China Standard Time"})]
        free = ev._compute_free_slots(events, self._day(), 9 * 60, 18 * 60)
        assert free == []

    def test_all_day_blocks_whole_day(self):
        """全天事件占掉整个窗口。"""
        events = [_event(id="1", isAllDay=True,
                         start={"dateTime": "2026-08-10T00:00:00", "timeZone": "UTC"},
                         end={"dateTime": "2026-08-11T00:00:00", "timeZone": "UTC"})]
        assert ev._compute_free_slots(events, self._day(), 9 * 60, 18 * 60) == []


class TestFormatFreeDay:
    """空闲结果显示 _format_free_day。

    三种形态：无空闲、整天空闲、列出具体时段，两种语言都要对。
    """

    def _free(self):
        """一段 09:00-10:30 的空闲。"""
        return [(datetime(2026, 8, 10, 9, 0), datetime(2026, 8, 10, 10, 30))]

    def test_no_free_slots(self):
        """没有空闲时两种语言各自的提示。"""
        set_lang("zh")
        assert "无空闲时段" in ev._format_free_day(date(2026, 8, 10), [], 9 * 60, 18 * 60)
        set_lang("en")
        assert "no free slots" in ev._format_free_day(date(2026, 8, 10), [], 9 * 60, 18 * 60)

    def test_free_all_day(self):
        """空闲盖满窗口时提示整天空闲。"""
        free = [(datetime(2026, 8, 10, 9, 0), datetime(2026, 8, 10, 18, 0))]
        set_lang("zh")
        assert "整天空闲" in ev._format_free_day(date(2026, 8, 10), free, 9 * 60, 18 * 60)
        set_lang("en")
        assert "free all day" in ev._format_free_day(date(2026, 8, 10), free, 9 * 60, 18 * 60)

    def test_free_slot_list(self):
        """列出具体空闲时段，格式是 HH:MM-HH:MM。"""
        set_lang("zh")
        assert "09:00-10:30" in ev._format_free_day(date(2026, 8, 10), self._free(), 9 * 60, 18 * 60)


class TestCheckConflicts:
    """冲突检测 _check_conflicts。

    add 时非 --force 调用：按窗口查询现有日程，找出与新日程重叠的那些。
    showAs=free 不算占用；定期系列只检查首次出现窗口（start 起 14 天内）。
    """

    def test_overlap_detected(self, monkeypatch):
        """与新日程重叠的现有日程会被查出来。"""
        events = [_event(id="1")]
        _mock_net(monkeypatch, get_all=lambda *a, **k: events)
        result = ev._check_conflicts("tk", datetime(2026, 8, 10, 9, 30),
                                     datetime(2026, 8, 10, 10, 30), False)
        assert len(result) == 1 and result[0][0]["id"] == "1"

    def test_free_not_counted(self, monkeypatch):
        """showAs=free 的日程不算占用，不构成冲突。"""
        events = [_event(id="1", showAs="free")]
        _mock_net(monkeypatch, get_all=lambda *a, **k: events)
        assert ev._check_conflicts("tk", datetime(2026, 8, 10, 9, 30),
                                   datetime(2026, 8, 10, 10, 30), False) == []

    def test_disjoint_empty(self, monkeypatch):
        """完全不重叠时结果为空。"""
        _mock_net(monkeypatch, get_all=lambda *a, **k: [_event(id="1")])
        assert ev._check_conflicts("tk", datetime(2026, 8, 10, 14, 0),
                                   datetime(2026, 8, 10, 15, 0), False) == []


class TestCmdAdd:
    """add 命令路径（mock 网络）。

    验证 POST 参数组装（时间、全天自动处理、默认 1 小时）、
    成功输出（含 🆔 行）、参数校验报错。
    """

    def _args(self, **kw):
        """构造 add 的参数，缺省字段补全，force=True 跳过冲突检查。"""
        base = dict(subject="新会议", start="2026-08-10 09:00", end="2026-08-10 10:00",
                    all_day=False, location=None, body=None, category=None, importance=None,
                    private=False, busy=None, remind=None, repeat=None, repeat_until=None,
                    repeat_times=None, force=True)
        base.update(kw)
        return _args(**base)

    def test_success_chinese(self, capsys, monkeypatch):
        """新建成功的中文输出，含 🆔 行，POST 载荷的时间组装正确。"""
        calls = {}
        def fake(method, endpoint, token, data=None, prefer_immutable=False):
            calls["data"] = data
            assert (method, endpoint) == ("POST", "/me/events")
            return _event(id="NEW1", subject=data["subject"])
        _mock_net(monkeypatch, call_fn=fake)
        assert ev.cmd_add(self._args()) == 0
        out = capsys.readouterr().out
        assert "✅ 已添加到日历" in out
        assert "🆔 NEW1" in out
        assert calls["data"]["start"]["dateTime"] == "2026-08-10T09:00:00"

    def test_success_english(self, capsys, monkeypatch, en):
        """新建成功的英文输出。"""
        def fake(method, endpoint, token, data=None, prefer_immutable=False):
            return _event(id="NEW1", subject=data["subject"])
        _mock_net(monkeypatch, call_fn=fake)
        assert ev.cmd_add(self._args()) == 0
        assert "✅ Added to calendar:" in capsys.readouterr().out

    def test_default_end_one_hour(self, monkeypatch):
        """没给结束时间时默认开始后 1 小时。

        用户只写开始时间是常见用法（"加个 9 点的会"），
        结束时间自动补成 10:00。
        """
        calls = {}
        def fake(method, endpoint, token, data=None, prefer_immutable=False):
            calls["data"] = data
            return _event()
        _mock_net(monkeypatch, call_fn=fake)
        ev.cmd_add(self._args(end=None))
        assert calls["data"]["end"]["dateTime"] == "2026-08-10T10:00:00"

    def test_date_only_becomes_all_day(self, monkeypatch):
        """只给日期时自动按全天处理。

        add 只给日期没给时间，默认是全天日程而不是报错，
        这是对"加个生日"这类场景的刻意设计。
        """
        calls = {}
        def fake(method, endpoint, token, data=None, prefer_immutable=False):
            calls["data"] = data
            return _event()
        _mock_net(monkeypatch, call_fn=fake)
        ev.cmd_add(self._args(start="2026-08-10", end=None))
        assert calls["data"]["isAllDay"] is True

    def test_end_before_start_raises(self, monkeypatch):
        """结束早于开始要报错，不能造出时间倒挂的日程。"""
        _mock_net(monkeypatch)
        with pytest.raises(CalError):
            ev.cmd_add(self._args(start="2026-08-10 10:00", end="2026-08-10 09:00"))

    def test_negative_remind_raises(self, monkeypatch):
        """提醒为负数要报错。"""
        _mock_net(monkeypatch)
        with pytest.raises(CalError):
            ev.cmd_add(self._args(remind=-1))

    def test_repeat_until_without_repeat_raises(self, monkeypatch):
        """截止条件没配 --repeat 要报错。

        --repeat-until / --repeat-times 是 --repeat 的附属参数，
        单独出现说明用户用法有误。
        """
        _mock_net(monkeypatch)
        with pytest.raises(CalError):
            ev.cmd_add(self._args(repeat_until="2026-12-31"))


class TestCmdUpdate:
    """update 命令路径（mock 网络）。

    验证无字段时的提示、PATCH 参数组装、时间校验。
    """

    def _args(self, **kw):
        """构造 update 的参数，所有字段默认 None（即不改）。"""
        base = dict(event_id="E1", subject=None, start=None, end=None, all_day=None,
                    location=None, body=None, category=None, importance=None, private=None,
                    busy=None, remind=None, no_remind=False, repeat=None, repeat_until=None,
                    repeat_times=None, yes=True)
        base.update(kw)
        return _args(**base)

    def test_no_fields_returns_1(self, capsys, monkeypatch):
        """一个字段都没给时提示并返回 1，不发 PATCH。

        用户可能误以为"不写参数=不改"，这里要明确告知。
        """
        _mock_net(monkeypatch)
        assert ev.cmd_update(self._args()) == 1
        assert "没有要修改的字段" in capsys.readouterr().out

    def test_change_subject(self, capsys, monkeypatch):
        """改标题：先 GET 原事件，再 PATCH 带上新值，输出成功。"""
        calls = {}
        def fake(method, endpoint, token, data=None, prefer_immutable=False):
            if method == "GET":
                return _event()
            calls["patch"] = data
            return _event(subject=data["subject"])
        _mock_net(monkeypatch, call_fn=fake)
        assert ev.cmd_update(self._args(subject="新标题")) == 0
        assert calls["patch"]["subject"] == "新标题"
        assert "✅ 已更新" in capsys.readouterr().out

    def test_time_validation(self, monkeypatch):
        """改时间时结束早于开始要报错。"""
        _mock_net(monkeypatch, call_fn=lambda *a, **k: _event())
        with pytest.raises(CalError):
            ev.cmd_update(self._args(start="2026-08-10 10:00", end="2026-08-10 09:00"))


class TestCmdDelete:
    """delete 命令路径（mock 网络）。

    验证单次/整系列的删除目标选择、输出文案、--json 结构化输出。
    """

    def test_delete_occurrence(self, capsys, monkeypatch):
        """删单次：DELETE 指向本次 ID，输出"移除本次出现"。"""
        deleted = []
        def fake(method, endpoint, token, data=None, prefer_immutable=False):
            if method == "GET":
                return _event()
            deleted.append(endpoint)
            return None
        _mock_net(monkeypatch, call_fn=fake)
        assert ev.cmd_delete(_args(event_id="E1", yes=True, series=False)) == 0
        assert "已从日历中移除本次出现" in capsys.readouterr().out
        assert deleted == ["/me/events/E1"]

    def test_delete_series(self, capsys, monkeypatch):
        """删整个系列：--series 指向主事件，输出带"整个系列"警告语义。"""
        master = _event(recurrence={"pattern": {"type": "daily", "interval": 1},
                                    "range": {"type": "noEnd"}})
        _mock_net(monkeypatch, call_fn=lambda *a, **k: master)
        assert ev.cmd_delete(_args(event_id="E1", yes=True, series=True)) == 0
        assert "整个系列" in capsys.readouterr().out

    def test_english(self, capsys, monkeypatch, en):
        """英文环境下的删除输出。"""
        _mock_net(monkeypatch, call_fn=lambda *a, **k: _event())
        ev.cmd_delete(_args(event_id="E1", yes=True, series=False))
        assert "Removed this occurrence" in capsys.readouterr().out

    def test_json_output(self, capsys, monkeypatch):
        """--json 模式下输出结构化结果，供程序消费。"""
        _mock_net(monkeypatch, call_fn=lambda *a, **k: _event())
        assert ev.cmd_delete(_args(event_id="E1", yes=True, series=False, json=True)) == 0
        out = json.loads(capsys.readouterr().out)
        assert out["deleted"] == "E1" and out["series"] is False


class TestCmdRead:
    """read 命令路径（mock 网络）。

    验证详情输出覆盖全部字段标记，以及定期系列单次出现的上下文
    （第 N 次 + 🆕 系列主事件ID）。
    """

    def test_full_details_fields(self, capsys, monkeypatch):
        """详情输出覆盖全部字段标记。

        每个标记对应一类信息：📋 标题、🆔 ID、🕐 时间、📍 地点、
        🕘 添加时间、👤 组织者、🏷️ 类别、⭐ 重要度、🔒 私密、
        📊 忙闲、📝 备注（HTML 清洗）、🔗 网页链接。
        """
        full = _event(
            id="E9", subject="完整日程", categories=["工作", "重要"], importance="high",
            sensitivity="private", showAs="tentative",
            body={"content": "<p>备注<b>内容</b></p>"},
            webLink="https://outlook.live.com/cal", createdDateTime="2026-08-01T09:00:00+08:00",
            organizer={"emailAddress": {"address": "a@example.com"}},
        )
        _mock_net(monkeypatch, call_fn=lambda *a, **k: full)
        assert ev.cmd_read(_args(event_id="E9")) == 0
        out = capsys.readouterr().out
        for mark in ("📋 完整日程", "🆔 E9", "🕐", "📍 3号会议室", "🕘 添加时间",
                     "👤 组织者", "🏷️ 工作, 重要", "⭐ 重要度: 高", "🔒 私密",
                     "📊 显示为: tentative", "📝 备注内容", "🔗 https://outlook.live.com/cal"):
            assert mark in out, mark

    def test_series_context(self, capsys, monkeypatch):
        """定期系列的单次出现要带出主事件上下文。

        用户 read 一个系列里的某次时，要能看到所属系列、第几次、
        以及可操作的 🆕 系列主事件ID。
        """
        occ = _event(id="O1", seriesMasterId="M1",
                     start={"dateTime": "2026-08-15T10:00:00", "timeZone": "China Standard Time"})
        master = _event(id="M1", subject="每月例会",
                        recurrence={"pattern": {"type": "absoluteMonthly", "interval": 1,
                                                "dayOfMonth": 15},
                                    "range": {"type": "noEnd", "startDate": "2026-08-15"}})
        def fake(method, endpoint, token, data=None, prefer_immutable=False):
            return master if endpoint.endswith("M1") else occ
        _mock_net(monkeypatch, call_fn=fake)
        ev.cmd_read(_args(event_id="O1"))
        out = capsys.readouterr().out
        assert "🆕 系列主事件ID: M1" in out
        assert "第 1 次出现" in out


class TestCmdList:
    """list 命令路径（mock 网络）。

    验证空结果提示、逐条 🆔 行、搜索无匹配提示、--json 纯净输出。
    """

    def _args(self, **kw):
        """构造 list 的参数，缺省字段补全。"""
        base = dict(days=7, past=0, search=None, category=None, summary=False,
                    from_date=None, created_after=None, reminders=False)
        base.update(kw)
        return _args(**base)

    def test_empty_result(self, capsys, monkeypatch):
        """没有日程时的提示，而不是报错。"""
        _mock_net(monkeypatch)
        assert ev.cmd_list(self._args()) == 0
        assert "没有符合条件的日程" in capsys.readouterr().out

    def test_events_with_id_lines(self, capsys, monkeypatch):
        """有日程时逐条显示标题和 🆔 行。"""
        _mock_net(monkeypatch, get_all=lambda *a, **k: [_event()])
        ev.cmd_list(self._args())
        out = capsys.readouterr().out
        assert "测试日程" in out and "🆔 E1" in out

    def test_search_no_match(self, capsys, monkeypatch):
        """搜索无匹配时给出明确提示（含筛选条件）。"""
        _mock_net(monkeypatch, get_all=lambda *a, **k: [_event()])
        ev.cmd_list(self._args(search="找不到"))
        assert "无匹配" in capsys.readouterr().out

    def test_json_purity(self, capsys, monkeypatch):
        """--json 输出必须是纯净 JSON，能被 json.loads 直接解析。"""
        _mock_net(monkeypatch, get_all=lambda *a, **k: [_event()])
        ev.cmd_list(self._args(json=True))
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data[0]["subject"] == "测试日程"
