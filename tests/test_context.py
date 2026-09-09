"""Agent-facing canonical inputs, clock context and timezone propagation, entirely offline."""
import json
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

import ocal_context as ctx
import ocal_events as ev
import ocal_graph as graph
import ocal_recurrence as recurrence
import ocal_time as tm
import outlook_cal
from test_events import _event


def run_cli(monkeypatch, argv, *, offline=False):
    def bootstrap():
        if offline:
            pytest.fail("Offline commands must not bootstrap network dependencies")
    monkeypatch.setattr(outlook_cal, "ensure_deps", bootstrap)
    monkeypatch.setattr(outlook_cal, "harden_stdio", lambda: None)
    monkeypatch.setattr(sys, "argv", ["outlook_cal.py", *argv])
    return outlook_cal.main()


@pytest.mark.parametrize("position", ["before", "after"])
def test_context_is_offline_and_timezone_explicit(monkeypatch, capsys, position):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 9, 8, 20, tzinfo=ZoneInfo("UTC")).astimezone(tz)

    monkeypatch.setattr(ctx, "datetime", Clock)
    monkeypatch.setattr(ev, "get_token", lambda: pytest.fail("Context must not authenticate"))
    monkeypatch.setattr(graph.requests, "request", lambda *a, **k: pytest.fail("No network"))
    argv = ["context", "--json"]
    if position == "before":
        argv[:0] = ["--timezone", "Asia/Shanghai"]
    else:
        argv += ["--timezone", "Asia/Shanghai"]
    assert run_cli(monkeypatch, argv, offline=True) == 0
    assert json.loads(capsys.readouterr().out) == {
        "now": "2026-09-09T04:00:00+08:00", "today": "2026-09-09",
        "timezone": "Asia/Shanghai", "utc_offset": "+08:00",
        "weekday": "wednesday", "week_start": "2026-09-07",
    }


@pytest.mark.parametrize("base,days,expected", [
    ("2026-09-07", 4, "2026-09-11"),
    ("2026-09-07", 7, "2026-09-14"),
    ("2026-01-01", -1, "2025-12-31"),
    ("2028-02-28", 1, "2028-02-29"),
    ("2028-02-29", 1, "2028-03-01"),
    ("2026-09-09", 0, "2026-09-09"),
])
def test_date_arithmetic_is_explicit_and_offline(monkeypatch, capsys, base, days, expected):
    monkeypatch.setattr(ev, "get_token", lambda: pytest.fail("Date arithmetic must not authenticate"))
    assert run_cli(monkeypatch, ["date", "--base", base, "--days", str(days), "--json"], offline=True) == 0
    assert json.loads(capsys.readouterr().out) == {"base": base, "days": days, "date": expected}


@pytest.mark.parametrize("argv", [
    ["context", "--timezone", "Mars/Olympus"],
    ["date", "--base", "今天", "--days", "1"],
    ["date", "--base", "2026-02-30", "--days", "1"],
    ["date", "--base", "9999-12-31", "--days", "1"],
    ["today"], ["tomorrow"], ["week"],
    ["free"], ["list", "--past", "7"], ["list"],
    ["list", "--from", "2026-09-09", "--created-before", ""],
    ["list", "--created-after", "2026-09-01", "--created-before", ""],
    ["free", "本周五"], ["free", "2026-09-11", "--from", ""],
    ["free", "9999-12-31"],
    ["add", "Missing end", "2026-09-11T09:00"],
    ["add", "Date only", "2026-09-11"],
    ["add", "Overflow", "9999-12-31", "--all-day"],
    ["add", "Invalid pattern", "2026-09-11T09:00", "2026-09-11T10:00", "--repeat", ""],
    ["add", "Invalid file", "2026-09-11T09:00", "2026-09-11T10:00", "--repeat-file", ""],
])
def test_obsolete_or_ambiguous_inputs_fail_without_network(monkeypatch, capsys, argv):
    monkeypatch.setattr(ev, "get_token", lambda: pytest.fail("Invalid arguments must not authenticate"))
    monkeypatch.setattr(graph.requests, "request", lambda *a, **k: pytest.fail("No network"))
    assert run_cli(monkeypatch, [*argv, "--json"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["exit"] == 1 and result["error"]


def test_timezone_reaches_payload_headers_and_is_restored(monkeypatch, capsys):
    originals = (tm.LOCAL_TZ, tm.LOCAL_TZ_NAME, ev.LOCAL_TZ, ev.LOCAL_TZ_NAME,
                 graph.LOCAL_TZ_NAME, recurrence.LOCAL_TZ_NAME)
    requests = []
    monkeypatch.setattr(ev, "get_token", lambda: "mock-token")

    class Response:
        status_code = 201
        def __init__(self, data):
            self.data = data
        def json(self):
            return {**_event(), **self.data}

    def request(method, url, headers, json, timeout):
        requests.append((method, headers, json))
        return Response(json)

    monkeypatch.setattr(graph.requests, "request", request)
    assert run_cli(monkeypatch, ["add", "Explicit", "2026-09-11T09:00", "2026-09-11T10:00",
                                 "--repeat", '{"type":"daily","interval":1}',
                                 "--force", "--timezone", "Asia/Urumqi", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["start"] == {"dateTime": "2026-09-11T09:00:00", "timeZone": "Asia/Urumqi"}
    assert requests[0][0] == "POST"
    assert 'outlook.timezone="Asia/Urumqi"' in requests[0][1]["Prefer"]
    assert result["recurrence"]["range"]["recurrenceTimeZone"] == "Asia/Urumqi"
    assert originals == (tm.LOCAL_TZ, tm.LOCAL_TZ_NAME, ev.LOCAL_TZ, ev.LOCAL_TZ_NAME,
                         graph.LOCAL_TZ_NAME, recurrence.LOCAL_TZ_NAME)


@pytest.mark.parametrize("start,end", [
    ("2026-03-08 02:30", "2026-03-08 03:30"),
    ("2026-11-01 01:30", "2026-11-01 02:30"),
])
def test_dst_ambiguity_and_nonexistent_times_do_not_write(monkeypatch, capsys, start, end):
    monkeypatch.setattr(ev, "get_token", lambda: "mock-token")
    monkeypatch.setattr(ev, "_call", lambda *a, **k: pytest.fail("No write for ambiguous times"))
    assert run_cli(monkeypatch, ["add", "DST", start, end, "--force",
                                 "--timezone", "America/New_York", "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["exit"] == 1


def test_repeat_file_is_structured_json(monkeypatch, capsys, tmp_path):
    pattern = {"type": "weekly", "interval": 1, "daysOfWeek": ["friday"], "firstDayOfWeek": "monday"}
    path = tmp_path / "pattern with spaces.json"
    path.write_text(json.dumps(pattern), encoding="utf-8")
    monkeypatch.setattr(ev, "get_token", lambda: "mock-token")
    monkeypatch.setattr(ev, "_call", lambda method, url, token, data=None, **kw: {**_event(), **data})
    assert run_cli(monkeypatch, ["add", "Weekly", "2026-09-11 09:00", "2026-09-11 10:00",
                                 "--repeat-file", str(path), "--repeat-times", "3", "--force", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["recurrence"]["pattern"] == pattern
    assert result["recurrence"]["range"]["numberOfOccurrences"] == 3


def test_all_day_recurrence_uses_mailbox_timezone(monkeypatch, capsys):
    monkeypatch.setattr(ev, "get_token", lambda: "mock-token")
    monkeypatch.setattr(ev, "_mailbox_tz_name", lambda token: ("China Standard Time", True))
    monkeypatch.setattr(ev, "_call", lambda method, url, token, data=None, **kw: {**_event(), **data})
    assert run_cli(monkeypatch, ["add", "All-day", "2026-09-11", "--all-day",
                                 "--repeat", '{"type":"daily","interval":1}',
                                 "--repeat-times", "2", "--timezone", "UTC", "--force", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["start"]["timeZone"] == result["end"]["timeZone"] == "China Standard Time"
    assert result["recurrence"]["range"]["recurrenceTimeZone"] == "China Standard Time"


@pytest.mark.parametrize("all_day", [False, True])
def test_move_overflow_is_a_json_error_without_patch(monkeypatch, capsys, all_day):
    monkeypatch.setattr(ev, "get_token", lambda: "mock-token")
    def call(method, *args, **kwargs):
        assert method == "GET"
        if all_day:
            return _event(start={"dateTime": "2026-09-11T00:00:00", "timeZone": "UTC"},
                          end={"dateTime": "2026-09-12T00:00:00", "timeZone": "UTC"}, isAllDay=True)
        return _event()
    monkeypatch.setattr(ev, "_call", call)
    assert run_cli(monkeypatch, ["move", "event-id", "--days", "999999999999", "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["exit"] == 1


@pytest.mark.parametrize("content", ["", "\ufeff", " \n\t"])
def test_empty_repeat_file_cannot_remove_existing_rule(monkeypatch, capsys, tmp_path, content):
    path = tmp_path / "empty.json"
    path.write_text(content, encoding="utf-8")
    monkeypatch.setattr(ev, "get_token", lambda: pytest.fail("Reject invalid file before authentication"))
    monkeypatch.setattr(ev, "_call", lambda *a, **k: pytest.fail("Must not clear recurrence"))
    assert run_cli(monkeypatch, ["update", "series-id", "--repeat-file", str(path), "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["exit"] == 1


@pytest.mark.parametrize("day,from_time,to_time", [
    ("2026-03-08", "00:00", "04:00"),  # Spring gap inside window.
    ("2026-11-01", "00:00", "04:00"),  # Fall fold inside window.
    ("2026-03-08", "02:30", "04:00"),  # Nonexistent boundary.
    ("2026-11-01", "01:30", "04:00"),  # Repeated boundary.
])
def test_free_does_not_report_ambiguous_dst_window_as_available(monkeypatch, capsys, day, from_time, to_time):
    monkeypatch.setattr(ev, "get_token", lambda: pytest.fail("Reject before querying"))
    assert run_cli(monkeypatch, ["free", day, "--from", from_time, "--to", to_time,
                                 "--timezone", "America/New_York", "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["exit"] == 1


def test_free_utc_retains_busy_hour_that_spans_a_local_fold(monkeypatch, capsys):
    monkeypatch.setattr(ev, "get_token", lambda: "mock-token")
    busy = _event(start={"dateTime": "2026-11-01T05:30:00Z", "timeZone": "UTC"},
                  end={"dateTime": "2026-11-01T06:30:00Z", "timeZone": "UTC"}, showAs="busy")
    monkeypatch.setattr(ev, "_get_all", lambda *a, **kw: [busy])
    assert run_cli(monkeypatch, ["free", "2026-11-01", "--from", "04:00", "--to", "09:00",
                                 "--timezone", "UTC", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {"2026-11-01": [["04:00", "05:30"], ["06:30", "09:00"]]}


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_json_summary_counts_start_dates_in_selected_timezone(monkeypatch, capsys, lang):
    monkeypatch.setattr(ev, "get_token", lambda: "mock-token")
    events = [
        _event(start={"dateTime": "2026-09-11T23:30:00", "timeZone": "UTC"}),
        _event(start={"dateTime": "2026-09-12T01:00:00", "timeZone": "UTC"}),
        _event(start={"dateTime": "2026-09-11T00:00:00", "timeZone": "UTC"},
               end={"dateTime": "2026-09-14T00:00:00", "timeZone": "UTC"}, isAllDay=True),
    ]
    monkeypatch.setattr(ev, "_get_all", lambda *a, **kw: events)
    assert run_cli(monkeypatch, ["list", "--from", "2026-09-11", "--days", "3", "--summary",
                                 "--timezone", "Asia/Shanghai", "--lang", lang, "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {"2026-09-11": 1, "2026-09-12": 2}


def test_json_summary_without_matches_is_empty_object(monkeypatch, capsys):
    monkeypatch.setattr(ev, "get_token", lambda: "mock-token")
    monkeypatch.setattr(ev, "_get_all", lambda *a, **kw: [])
    assert run_cli(monkeypatch, ["list", "--from", "2026-09-11", "--summary", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {}
