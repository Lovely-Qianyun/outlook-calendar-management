"""输出协议解析测试：用 agent/脚本实际使用的提取正则验证输出契约。

SKILL 与 protocol-eval.md 承诺的解析方式在这里逐条钉住：
- list 🆔 4 空格、add 🆔 3 空格、read 🆔 顶格、🆕 系列主事件ID 行
- free 的 HH:MM-HH:MM 时段格式
- 冲突警告等非交互提示不进 stdout（stdout 的 🆔 只属于结果事件）
- zh/en 锚点完全一致；--json 错误形状 {"error", "exit": 1}
"""
import json
import re
from datetime import date

import ocal_events as ev
from ocal_i18n import set_lang
from test_events import _args, _event, _mock_net

# 协议承诺的正则（与 tests/protocol-eval.md 保持一致，改动必须两处同步）
ID_LIST = re.compile(r"^    🆔 (.+)$", re.M)          # list：4 空格
ID_ADD = re.compile(r"^   🆔 (.+)$", re.M)            # add：3 空格
ID_READ = re.compile(r"^🆔 (.+)$", re.M)              # read：顶格
ID_MASTER = re.compile(r"^🆕 系列主事件ID: (.+)$", re.M)
SLOTS = re.compile(r"(\d{2}:\d{2})-(\d{2}:\d{2})")


def _add_args(**kw):
    """构造 add 的完整参数（缺省字段补全，force 跳过冲突检查）。"""
    base = dict(subject="新会议", start="2026-08-10 09:00", end="2026-08-10 10:00",
                all_day=False, location=None, body=None, category=None, importance=None,
                private=False, busy=None, remind=None, repeat=None, repeat_until=None,
                repeat_times=None, force=True)
    base.update(kw)
    return _args(**base)


class TestIdAnchors:
    """🆔/🆕 锚点的缩进契约：agent 提取 ID 的唯一来源。"""

    def test_list_id_extraction(self, capsys, monkeypatch):
        """list 的 🆔 行 4 空格缩进，逐条可提取。"""
        _mock_net(monkeypatch, get_all=lambda *a, **k: [_event(id="L1"), _event(id="L2")])
        ev.cmd_list(_args(days=7, past=0))
        out = capsys.readouterr().out
        assert ID_LIST.findall(out) == ["L1", "L2"]

    def test_add_id_extraction(self, capsys, monkeypatch):
        """add 的 🆔 行 3 空格缩进，且是新日程自己的 ID。"""
        def fake(method, endpoint, token, data=None, prefer_immutable=False):
            return _event(id="NEW1", subject=data["subject"])
        _mock_net(monkeypatch, call_fn=fake)
        ev.cmd_add(_add_args())
        out = capsys.readouterr().out
        assert ID_ADD.findall(out) == ["NEW1"]

    def test_read_id_and_master(self, capsys, monkeypatch):
        """read 的 🆔 顶格；定期单次附带 🆕 系列主事件ID 行。"""
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
        assert ID_READ.findall(out) == ["O1"]
        assert ID_MASTER.findall(out) == ["M1"]

    def test_anchors_language_independent(self, capsys, monkeypatch):
        """英文环境下锚点与中文完全一致，提取正则不变。"""
        set_lang("en")
        def fake(method, endpoint, token, data=None, prefer_immutable=False):
            return _event(id="NEW1", subject=data["subject"])
        _mock_net(monkeypatch, call_fn=fake)
        ev.cmd_add(_add_args(subject="Meet"))
        out = capsys.readouterr().out
        assert ID_ADD.findall(out) == ["NEW1"]
        set_lang("zh")

    def test_stdout_ids_only_result(self, capsys, monkeypatch):
        """冲突警告（带现有日程 🆔）在 stderr：stdout 的 🆔 只能属于新日程。"""
        def fake(method, endpoint, token, data=None, prefer_immutable=False):
            if method == "POST":
                return _event(id="NEW1", subject=data["subject"])
            return _event()
        monkeypatch.setattr(ev, "get_token", lambda: "tk")
        monkeypatch.setattr(ev, "_call", fake)
        monkeypatch.setattr(ev, "_get_all", lambda *a, **k: [_event(id="OLD1")])
        ev.cmd_add(_add_args(force=False, start="2026-08-10 09:30", end="2026-08-10 10:30"))
        cap = capsys.readouterr()
        assert ID_ADD.findall(cap.out) == ["NEW1"]  # stdout 只有结果事件
        assert "OLD1" in cap.err                    # 现有日程只在 stderr


class TestFreeSlots:
    """free 输出的 HH:MM-HH:MM 时段格式。"""

    def test_slot_format(self, monkeypatch):
        """有空闲有空闲段时，时段逐段可解析成 HH:MM-HH:MM。"""
        set_lang("zh")
        busy = [_event(id="1", start={"dateTime": "2026-08-10T12:00:00", "timeZone": "China Standard Time"},
                       end={"dateTime": "2026-08-10T13:00:00", "timeZone": "China Standard Time"})]
        free = ev._compute_free_slots(busy, date(2026, 8, 10), 9 * 60, 18 * 60)
        line = ev._format_free_day(date(2026, 8, 10), free, 9 * 60, 18 * 60)
        assert SLOTS.findall(line) == [("09:00", "12:00"), ("13:00", "18:00")]

    def test_no_free_and_all_free_shapes(self, monkeypatch):
        """无空闲/整天空闲两种形态不含伪时段，agent 需按形态文案分支处理。"""
        set_lang("zh")
        no_free = ev._format_free_day(date(2026, 8, 10), [], 9 * 60, 18 * 60)
        assert "无空闲时段" in no_free and SLOTS.findall(no_free) == []
        all_free = ev._format_free_day(date(2026, 8, 10),
                                       ev._compute_free_slots([], date(2026, 8, 10), 9 * 60, 18 * 60),
                                       9 * 60, 18 * 60)
        assert "整天空闲" in all_free and SLOTS.findall(all_free) == []


class TestJsonMode:
    """--json 的纯净性契约。"""

    def test_json_error_shape_via_cli(self, capsys, monkeypatch):
        """出错时 stdout 是 {"error", "exit": 1}，可 json.loads，退出码 1。"""
        import sys as _sys
        import outlook_cal
        monkeypatch.setattr(outlook_cal, "ensure_deps", lambda: None)
        monkeypatch.setattr(outlook_cal, "harden_stdio", lambda: None)
        _mock_net(monkeypatch)  # get_token → "tk"
        monkeypatch.setattr(_sys, "argv", ["outlook_cal.py", "--json", "add", "x",
                                           "2026-08-10 10:00", "2026-08-10 09:00"])
        code = outlook_cal.main()
        cap = capsys.readouterr()
        data = json.loads(cap.out)
        assert code == 1
        assert data["exit"] == 1
        assert "error" in data

    def test_json_error_not_on_stdout_human_text(self, capsys, monkeypatch):
        """--json 错误信息在 stderr 没有人类 ❌ 行；stdout 只有 JSON。"""
        import sys as _sys
        import outlook_cal
        monkeypatch.setattr(outlook_cal, "ensure_deps", lambda: None)
        monkeypatch.setattr(outlook_cal, "harden_stdio", lambda: None)
        _mock_net(monkeypatch)
        monkeypatch.setattr(_sys, "argv", ["outlook_cal.py", "--json", "add", "x",
                                           "2026-08-10 10:00", "2026-08-10 09:00"])
        outlook_cal.main()
        cap = capsys.readouterr()
        json.loads(cap.out)  # 纯净可解析
        assert "❌" not in cap.out
