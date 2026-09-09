"""输出协议解析测试：用 agent/脚本实际使用的提取正则验证输出契约。

SKILL 与 protocol-eval.md 承诺的解析方式在这里逐条钉住：
- list 🆔 4 空格、add 🆔 3 空格、read 🆔 顶格、🆕 行（锚点+冒号结构）的主事件 ID
- free 的 HH:MM-HH:MM 时段格式
- 冲突警告等非交互提示不进 stdout（stdout 的 🆔 只属于结果事件）
- 协议只到结构层（锚点/缩进/冒号/括号/时段/JSON 结构）：行内自然语言文案随语言，不属于协议
- zh/en 锚点完全一致；--json 错误形状 {"error", "exit": 1}
"""
import json
import io
import re
import sys
from datetime import date

import pytest

import ocal_events as ev
from ocal_errors import CalError
from ocal_i18n import set_lang, t
from test_events import _args, _event, _mock_net

# 协议承诺的正则（与 tests/protocol-eval.md 保持一致，改动必须两处同步）
ID_LIST = re.compile(r"^    🆔 (.+)$", re.M)          # list：4 空格
ID_ADD = re.compile(r"^   🆔 (.+)$", re.M)            # add：3 空格
ID_READ = re.compile(r"^🆔 (.+)$", re.M)              # read：顶格
ID_MASTER = re.compile(r"^🆕 .+?: (.+)$", re.M)  # 🆕 锚点+冒号结构：前缀文案随语言（zh: 系列主事件ID / en: Series master event ID）
SLOTS = re.compile(r"(\d{2}:\d{2})-(\d{2}:\d{2})")


def _add_args(**kw):
    """构造 add 的完整参数（缺省字段补全，force 跳过冲突检查）。"""
    base = dict(subject="新会议", start="2026-08-10 09:00", end="2026-08-10 10:00",
                all_day=False, location=None, body=None, category=None, importance=None,
                private=False, busy=None, remind=None, repeat=None, repeat_until=None,
                repeat_times=None, force=True)
    base.update(kw)
    return _args(**base)


def _run_cli(monkeypatch, argv, *, bootstrap=False):
    """运行真实参数解析/分发/错误边界，跳过依赖安装和 stdio 重配置。"""
    import outlook_cal
    if not bootstrap:
        monkeypatch.setattr(outlook_cal, "ensure_deps", lambda: None)
    monkeypatch.setattr(outlook_cal, "harden_stdio", lambda: None)
    monkeypatch.setattr(sys, "argv", ["outlook_cal.py", *argv])
    return outlook_cal.main()


class TestIdAnchors:
    """🆔/🆕 锚点的缩进契约：agent 提取 ID 的唯一来源。"""

    def test_list_id_extraction(self, capsys, monkeypatch):
        """list 的 🆔 行 4 空格缩进，逐条可提取。"""
        _mock_net(monkeypatch, get_all=lambda *a, **k: [_event(id="L1"), _event(id="L2")])
        ev.cmd_list(_args(days=7, from_date="2026-08-10"))
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

    def test_master_id_language_independent(self, capsys, monkeypatch):
        """英文环境下 🆕 行文案不同（Series master event ID），但锚点+冒号结构不变，同一正则仍可提取。"""
        set_lang("en")
        occ = _event(id="O1", seriesMasterId="M1",
                     start={"dateTime": "2026-08-15T10:00:00", "timeZone": "China Standard Time"})
        master = _event(id="M1", subject="Monthly sync",
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
        set_lang("zh")

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
        """无空闲/整天空闲两种形态不含伪时段：时段列表为空即判定（结构层，不依赖文案）。"""
        set_lang("zh")
        no_free = ev._format_free_day(date(2026, 8, 10), [], 9 * 60, 18 * 60)
        assert SLOTS.findall(no_free) == []
        all_free = ev._format_free_day(date(2026, 8, 10),
                                       ev._compute_free_slots([], date(2026, 8, 10), 9 * 60, 18 * 60),
                                       9 * 60, 18 * 60)
        assert SLOTS.findall(all_free) == []

    def test_free_shapes_language_independent(self, monkeypatch):
        """en 环境下无空闲/整天空闲同样无时段列表：结构判定与语言无关。"""
        set_lang("en")
        no_free = ev._format_free_day(date(2026, 8, 10), [], 9 * 60, 18 * 60)
        assert SLOTS.findall(no_free) == []
        all_free = ev._format_free_day(date(2026, 8, 10),
                                       ev._compute_free_slots([], date(2026, 8, 10), 9 * 60, 18 * 60),
                                       9 * 60, 18 * 60)
        assert SLOTS.findall(all_free) == []
        set_lang("zh")


class TestJsonMode:
    """--json 的纯净性契约。"""

    @pytest.mark.parametrize("lang", ["zh", "en"])
    @pytest.mark.parametrize("kind", ["single", "occurrence", "master"])
    @pytest.mark.parametrize("fail_patch", [False, True])
    @pytest.mark.parametrize("json_after_command", [False, True])
    def test_move_json_result_or_error(self, capsys, monkeypatch, lang, kind,
                                       fail_patch, json_after_command):
        """普通/系列/单次移动：成功与 PATCH 失败都只有一个 JSON，提示只在 stderr。"""
        event = _event(id="TARGET", subject="会议 🗓️",
                       type={"single": "singleInstance", "occurrence": "occurrence",
                             "master": "seriesMaster"}[kind],
                       seriesMasterId="MASTER" if kind == "occurrence" else None,
                       recurrence={"pattern": {"type": "daily", "interval": 1},
                                   "range": {"type": "noEnd", "startDate": "2026-08-10"}}
                       if kind == "master" else None)
        calls = []

        def fake(method, endpoint, token, data=None, prefer_immutable=False):
            calls.append((method, endpoint, data))
            if method == "GET":
                return event
            if fail_patch:
                raise CalError("Graph rejected update: 日程 🗓️")
            return {**event, **data}

        _mock_net(monkeypatch, call_fn=fake)
        argv = ["--lang", lang, "move", "TARGET", "--days", "1"]
        argv.insert(3 if json_after_command else 0, "--json")
        code = _run_cli(monkeypatch, argv)
        cap = capsys.readouterr()
        result = json.loads(cap.out)
        assert [(method, endpoint) for method, endpoint, _ in calls] == [
            ("GET", "/me/events/TARGET"), ("PATCH", "/me/events/TARGET")]
        if fail_patch:
            assert code == 1
            assert result == {"error": "Graph rejected update: 日程 🗓️", "exit": 1}
        else:
            assert code == 0
            assert result["id"] == "TARGET"
            assert result["subject"] == event["subject"]
            assert result["start"]["dateTime"] == "2026-08-11T09:00:00"
            assert result["end"]["dateTime"] == "2026-08-11T10:00:00"
        if kind == "single":
            assert cap.err == ""
        else:
            assert t("warn_move_occ" if kind == "occurrence" else "warn_move_series") in cap.err

    @pytest.mark.parametrize("lang", ["zh", "en"])
    def test_update_without_fields_returns_json_error_without_write(self, capsys, monkeypatch, lang):
        """无修改字段也遵守错误对象协议，且不能发出 PATCH。"""
        calls = []

        def fake(method, endpoint, token, data=None, prefer_immutable=False):
            calls.append(method)
            return _event()

        _mock_net(monkeypatch, call_fn=fake)
        code = _run_cli(monkeypatch, ["update", "E1", "--json", "--lang", lang])
        cap = capsys.readouterr()
        assert code == 1
        assert json.loads(cap.out) == {"error": t("warn_nothing_to_update"), "exit": 1}
        assert calls == ["GET"]
        assert cap.err == ""

    @pytest.mark.parametrize("lang", ["zh", "en"])
    @pytest.mark.parametrize("argv", [[], ["read"], ["list", "--days", "bad"], ["unknown"]])
    def test_argument_errors_are_json(self, capsys, monkeypatch, lang, argv):
        """缺参数、非法类型和未知命令均通过入口统一输出 JSON 错误。"""
        _mock_net(monkeypatch, call_fn=lambda *a, **k: pytest.fail("No network on parser errors"))
        code = _run_cli(monkeypatch, ["--lang", lang, "--json", *argv])
        cap = capsys.readouterr()
        result = json.loads(cap.out)
        assert code == result["exit"] == 1
        assert result["error"]
        assert cap.err == ""

    @pytest.mark.parametrize("option", ["--js", "--json=invalid"])
    def test_json_option_edge_cases_keep_structured_errors(self, capsys, monkeypatch, option):
        """argparse 接受的缩写和非法 flag 赋值都不能绕过 JSON 错误边界。"""
        code = _run_cli(monkeypatch, [option, "read"])
        result = json.loads(capsys.readouterr().out)
        assert code == result["exit"] == 1

    def test_literal_json_positional_does_not_enable_json_mode(self, capsys, monkeypatch):
        """-- 之后的 --json 是普通事件 ID，不能被入口误判为输出选项。"""
        _mock_net(monkeypatch, call_fn=lambda *a, **k: _event(id="--json"))
        assert _run_cli(monkeypatch, ["read", "--", "--json"]) == 0
        assert ID_READ.findall(capsys.readouterr().out) == ["--json"]

    @pytest.mark.parametrize("lang", ["zh", "en"])
    def test_bootstrap_failure_is_json(self, capsys, monkeypatch, lang):
        """依赖安装失败仍保留 stderr 诊断并输出 JSON 错误；不实际安装依赖。"""
        import ocal_bootstrap
        from types import SimpleNamespace

        monkeypatch.setattr(ocal_bootstrap, "_missing", lambda: ["requests"])
        monkeypatch.setattr(ocal_bootstrap.subprocess, "run", lambda *a, **k:
                            SimpleNamespace(returncode=1, stderr="offline installation failure"))
        code = _run_cli(monkeypatch, ["--lang", lang, "--json", "status"], bootstrap=True)
        cap = capsys.readouterr()
        assert code == 1
        assert json.loads(cap.out) == {"error": t("deps_fail_code", code=1), "exit": 1}
        assert "offline installation failure" in cap.err

    @pytest.mark.parametrize("lang", ["zh", "en"])
    @pytest.mark.parametrize("fail_read", [False, True])
    def test_json_preserves_unicode_through_gbk_pipe(self, monkeypatch, lang, fail_read):
        """Windows GBK 管道不能替换日程/错误中的 Unicode 字符。"""
        subject = "会议 🗓️ café"

        def fake(*a, **k):
            if fail_read:
                raise CalError(subject)
            return _event(subject=subject)

        _mock_net(monkeypatch, call_fn=fake)
        buffer = io.BytesIO()
        stream = io.TextIOWrapper(buffer, encoding="gbk", errors="replace")
        monkeypatch.setattr(sys, "stdout", stream)
        code = _run_cli(monkeypatch, ["--lang", lang, "read", "E1", "--json"])
        stream.flush()
        output = buffer.getvalue().decode("gbk")
        result = json.loads(output)
        assert result["error" if fail_read else "subject"] == subject
        assert code == int(fail_read)
        assert output.isascii()

    @pytest.mark.parametrize("argv", [["--json", "--help"], ["--json", "move", "--help"]])
    def test_explicit_help_remains_text(self, capsys, monkeypatch, argv):
        """显式帮助是 JSON 输出的例外，保持 argparse 的文本帮助与退出码 0。"""
        with pytest.raises(SystemExit) as exc:
            _run_cli(monkeypatch, argv)
        assert exc.value.code == 0
        assert "--json" in capsys.readouterr().out

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
