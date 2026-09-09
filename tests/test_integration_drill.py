"""Offline verification of the optional live runner's write and cleanup boundaries."""
import copy
import importlib.util
import json
import subprocess
from pathlib import Path
from datetime import date, timedelta

import pytest


SPEC = importlib.util.spec_from_file_location(
    "integration_drill", Path(__file__).parent / "integration" / "drill.py")
drill = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(drill)


class FakeClient:
    def __init__(self, account="test@example.com", fail=None, switch_on=None):
        self.account = account
        self.fail = fail
        self.switch_on = switch_on
        self.calls = []
        self.events = {"existing-personal-event": {"id": "existing-personal-event",
                                                   "subject": "Untouched personal event",
                                                   "start": {"dateTime": "2026-10-08T14:00:00", "timeZone": "UTC"},
                                                   "end": {"dateTime": "2026-10-08T15:00:00", "timeZone": "UTC"}}}
        self.counter = 0

    def call(self, *args):
        self.calls.append(args)
        command = args[0]
        if command == self.switch_on:
            self.account = "different@example.com"
        if command == self.fail:
            raise drill.DrillError(f"Simulated {command} failure")
        if command == "status":
            return {"connected": True, "account": self.account}
        if command == "context":
            return {"today": "2026-09-08", "timezone": "UTC", "utc_offset": "+00:00"}
        if command == "date":
            return {"date": "2026-10-08"}
        if command == "add":
            self.counter += 1
            event_id = f"created-{self.counter}"
            event = {"id": event_id, "subject": args[1],
                     "start": {"dateTime": args[2] + ":00.0000000", "timeZone": "UTC"},
                     "end": {"dateTime": args[3] + ":00.0000000", "timeZone": "UTC"}}
            if "--repeat" in args:
                event["recurrence"] = {"pattern": json.loads(args[args.index("--repeat") + 1]),
                                       "range": {"numberOfOccurrences": 2}}
            self.events[event_id] = event
            return copy.deepcopy(event)
        if command == "read":
            return copy.deepcopy(self.events[args[1]])
        if command == "update":
            self.events[args[1]]["subject"] = args[args.index("--subject") + 1]
            return copy.deepcopy(self.events[args[1]])
        if command == "move":
            day = args[args.index("--to") + 1]
            for bound in ("start", "end"):
                old = self.events[args[1]][bound]["dateTime"]
                self.events[args[1]][bound]["dateTime"] = day + old[10:]
            return copy.deepcopy(self.events[args[1]])
        if command == "list":
            prefix = args[args.index("--search") + 1] if "--search" in args else ""
            window_start = date.fromisoformat(args[args.index("--from") + 1])
            window_end = window_start + timedelta(days=int(args[args.index("--days") + 1]))
            results = []
            for source in self.events.values():
                if not source["subject"].startswith(prefix):
                    continue
                count = source.get("recurrence", {}).get("range", {}).get("numberOfOccurrences", 1)
                for offset in range(count):
                    event = copy.deepcopy(source)
                    if "recurrence" in event:
                        event.update(id=f"{source['id']}-occurrence-{offset}", seriesMasterId=source["id"])
                        for bound in ("start", "end"):
                            raw = event[bound]["dateTime"]
                            shifted = (date.fromisoformat(raw[:10]) + timedelta(days=offset)).isoformat()
                            event[bound]["dateTime"] = shifted + raw[10:]
                    if window_start <= date.fromisoformat(event["start"]["dateTime"][:10]) < window_end:
                        results.append(event)
            return results
        if command == "free":
            return {args[1]: [["14:00", "17:00"]]}
        if command == "delete":
            del self.events[args[1]]
            return {"deleted": args[1]}
        raise AssertionError(f"Unexpected command: {args}")


def test_confirmation_required_before_any_client_call():
    client = FakeClient()
    result = drill.Drill(client, "test@example.com").run()
    assert not result["ok"]
    assert client.calls == []


def test_wrong_account_prevents_writes_and_cleanup():
    client = FakeClient(account="real@example.com")
    result = drill.Drill(client, "test@example.com", confirm=True).run()
    assert not result["ok"]
    assert client.calls == [("status",)]
    assert list(client.events) == ["existing-personal-event"]


def test_success_cleans_only_returned_create_ids():
    client = FakeClient()
    result = drill.Drill(client, "TEST@example.com", confirm=True).run()
    assert result["ok"], result
    assert result["remaining_ids"] == result["unknown_create_subjects"] == []
    assert result["checks"] == ["context", "date", "add", "read", "update", "move",
                                 "list", "free", "recurrence", "recurrence_expansion", "delete_verified"]
    assert result["test_window"] == {"from": "2026-10-08", "days": 3, "timezone": "UTC"}
    assert result["deletion_checks"] == [
        {"id": "created-1", "status": "absent", "matching_ids": []},
        {"id": "created-2", "status": "absent", "matching_ids": []},
    ]
    assert list(client.events) == ["existing-personal-event"]
    assert [a[1] for a in client.calls if a[0] == "delete"] == ["created-2", "created-1"]
    for i, call in enumerate(client.calls):
        if call[0] in ("add", "update", "move", "delete"):
            assert client.calls[i - 1] == ("status",)


def test_failure_still_cleans_known_ids():
    client = FakeClient(fail="update")
    result = drill.Drill(client, "test@example.com", confirm=True).run()
    assert not result["ok"]
    assert [a[1] for a in client.calls if a[0] == "delete"] == ["created-1"]
    assert result["remaining_ids"] == []
    assert list(client.events) == ["existing-personal-event"]


def test_account_switch_stops_cleanup_and_reports_remaining_ids():
    client = FakeClient(fail="update", switch_on="update")
    result = drill.Drill(client, "test@example.com", confirm=True).run()
    assert not result["ok"]
    assert result["remaining_ids"] == ["created-1"]
    assert not any(a[0] == "delete" for a in client.calls)
    assert "existing-personal-event" in client.events


def test_unconfirmed_creation_is_not_retried_or_deleted_by_search():
    client = FakeClient(fail="add")
    result = drill.Drill(client, "test@example.com", confirm=True).run()
    assert not result["ok"]
    assert result["unknown_create_subjects"] == [result["subject_prefix"] + "timed"]
    assert result["remaining_ids"] == []
    assert sum(a[0] == "add" for a in client.calls) == 1
    assert not any(a[0] == "delete" for a in client.calls)
    assert [a for a in client.calls if a[0] == "list"] == [
        ("list", "--from", "2026-10-08", "--days", "3", "--search", result["subject_prefix"] + "timed")]
    assert result["unknown_create_checks"][0]["status"] == "not_found"


def test_cleanup_failure_reports_ids_without_retry():
    client = FakeClient(fail="delete")
    result = drill.Drill(client, "test@example.com", confirm=True).run()
    assert not result["ok"]
    assert result["remaining_ids"] == ["created-1", "created-2"]
    assert [a[1] for a in client.calls if a[0] == "delete"] == ["created-2", "created-1"]


def test_cli_uses_argument_list_utf8_json_and_explicit_timezone(monkeypatch):
    captured = []

    def run(command, **kwargs):
        captured.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, json.dumps({"subject": "中文"}), "")

    monkeypatch.setattr(drill.subprocess, "run", run)
    subject = 'subject with spaces "quotes" & symbols'
    assert drill.CalendarClient(lang="zh").call("add", subject)["subject"] == "中文"
    command, kwargs = captured[0]
    assert command[-2:] == ["add", subject]
    assert command[command.index("--timezone") + 1] == "UTC"
    assert command[command.index("--lang") + 1] == "zh"
    assert "--json" in command and kwargs["encoding"] == "utf-8"
    assert kwargs.get("shell", False) is False


def test_cli_timeout_has_no_retry(monkeypatch):
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(drill.subprocess, "run", run)
    with pytest.raises(drill.DrillError, match="outcome may be unknown; no retry"):
        drill.CalendarClient().call("add", "subject")
    assert len(calls) == 1


def test_readback_does_not_accept_equal_wall_times_in_a_different_zone():
    client = FakeClient()
    client.events["created-1"] = {
        "id": "created-1", "subject": "test",
        "start": {"dateTime": "2026-10-08T14:00:00.0000000", "timeZone": "China Standard Time"},
        "end": {"dateTime": "2026-10-08T15:00:00.0000000", "timeZone": "China Standard Time"},
    }
    with pytest.raises(drill.DrillError, match="timezone is not UTC"):
        drill.Drill(client, "test@example.com", True).check_event(
            "created-1", "test", "2026-10-08T14:00", "2026-10-08T15:00")


def test_unknown_create_is_observed_but_never_retried_or_automatically_deleted():
    class UnknownCreateClient(FakeClient):
        def call(self, *args):
            result = super().call(*args)
            if args[0] == "add":
                raise drill.DrillError("Response was lost after creation")
            return result

    client = UnknownCreateClient()
    result = drill.Drill(client, "test@example.com", True).run()
    assert not result["ok"]
    observed = result["unknown_create_checks"][0]
    assert observed["status"] == "observed"
    assert observed["matches"][0]["id"] == "created-1"
    assert observed["requested"] == {"start": "2026-10-08T14:00", "end": "2026-10-08T15:00"}
    assert result["remaining_ids"] == []
    assert len(result["unknown_create_subjects"]) == 1
    assert sum(a[0] == "add" for a in client.calls) == 1
    assert not any(a[0] == "delete" for a in client.calls)
    assert set(client.events) == {"existing-personal-event", "created-1"}


def test_unknown_create_inspection_does_not_read_a_changed_account():
    client = FakeClient(fail="add", switch_on="add")
    result = drill.Drill(client, "test@example.com", True).run()
    assert result["unknown_create_checks"][0]["status"] == "unverified"
    assert "Account mismatch" in result["unknown_create_checks"][0]["error"]
    assert not any(a[0] in ("list", "delete") for a in client.calls)


def test_unknown_subject_search_filters_out_non_exact_matches():
    class SimilarSubjectClient(FakeClient):
        def call(self, *args):
            result = super().call(*args)
            if args[0] == "add":
                self.events[result["id"]]["subject"] += "-different"
                raise drill.DrillError("Create result unknown")
            return result

    result = drill.Drill(SimilarSubjectClient(), "test@example.com", True).run()
    assert result["unknown_create_checks"][0]["status"] == "not_found"
    assert result["unknown_create_checks"][0]["matches"] == []


def test_delete_acknowledgement_does_not_replace_absence_check():
    class FalseDeleteClient(FakeClient):
        def call(self, *args):
            if args[0] == "delete":
                self.calls.append(args)
                # Different subjects must not hide surviving IDs or occurrences.
                self.events[args[1]]["subject"] = "unexpectedly renamed"
                return {"deleted": args[1]}
            return super().call(*args)

    client = FalseDeleteClient()
    result = drill.Drill(client, "test@example.com", True).run()
    assert not result["ok"]
    assert result["remaining_ids"] == ["created-1", "created-2"]
    checks = {check["id"]: check for check in result["deletion_checks"]}
    assert checks["created-1"]["matching_ids"] == ["created-1"]
    assert checks["created-2"]["matching_ids"] == ["created-2-occurrence-0", "created-2-occurrence-1"]
    assert all(check["status"] == "present" for check in checks.values())
    assert "delete_verified" not in result["checks"]
    assert "existing-personal-event" in client.events


def test_failed_cleanup_readback_never_repeats_acknowledged_deletes():
    class FailedReadbackClient(FakeClient):
        def call(self, *args):
            if args[0] == "list" and "--search" not in args:
                self.calls.append(args)
                raise drill.DrillError("Cleanup list failed")
            return super().call(*args)

    client = FailedReadbackClient()
    runner = drill.Drill(client, "test@example.com", True)
    result = runner.run()
    assert not result["ok"]
    assert result["remaining_ids"] == ["created-1", "created-2"]
    assert all(check["status"] == "unverified" for check in result["deletion_checks"])
    runner.cleanup()
    assert [a[1] for a in client.calls if a[0] == "delete"] == ["created-2", "created-1"]
    assert list(client.events) == ["existing-personal-event"]


def test_unknown_delete_result_is_checked_without_another_delete():
    class LostDeleteResponseClient(FakeClient):
        def call(self, *args):
            result = super().call(*args)
            if args[0] == "delete":
                raise drill.DrillError("Delete response was lost")
            return result

    client = LostDeleteResponseClient()
    result = drill.Drill(client, "test@example.com", True).run()
    assert not result["ok"]  # Preserve the transport error despite confirmed absence.
    assert result["remaining_ids"] == []
    assert all(check["status"] == "absent" for check in result["deletion_checks"])
    assert [a[1] for a in client.calls if a[0] == "delete"] == ["created-2", "created-1"]


@pytest.mark.parametrize("issue", ["missing", "extra", "wrong_time"])
def test_recurring_expansion_validates_count_and_times(issue):
    class IncorrectExpansionClient(FakeClient):
        def call(self, *args):
            result = super().call(*args)
            if args[0] == "list" and "--search" in args and args[-1].endswith("series"):
                if issue == "missing":
                    result.pop()
                elif issue == "extra":
                    result.append(copy.deepcopy(result[0]))
                else:
                    result[1]["start"]["dateTime"] = "2026-10-09T13:00:00"
            return result

    client = IncorrectExpansionClient()
    result = drill.Drill(client, "test@example.com", True).run()
    assert not result["ok"]
    assert "recurrence" in result["checks"]
    assert "recurrence_expansion" not in result["checks"]
    assert result["remaining_ids"] == []
    assert list(client.events) == ["existing-personal-event"]
