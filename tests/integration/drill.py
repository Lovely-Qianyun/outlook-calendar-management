"""Optional live smoke test. Only deletes IDs returned by this run's creates.

Normal pytest runs exercise this runner with a fake client; they never call Graph.
"""
import argparse
import json
import re
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4


CLI = Path(__file__).resolve().parents[2] / "scripts" / "outlook_cal.py"


class DrillError(RuntimeError):
    pass


class CalendarClient:
    def __init__(self, lang="en", timeout=90):
        self.lang = lang
        self.timeout = timeout

    def call(self, *args):
        command = [sys.executable, "-X", "utf8", str(CLI), "--json",
                   "--lang", self.lang, "--timezone", "UTC", *args]
        try:
            result = subprocess.run(command, capture_output=True, text=True,
                                    encoding="utf-8", timeout=self.timeout,
                                    stdin=subprocess.DEVNULL, check=False)
        except subprocess.TimeoutExpired as exc:
            raise DrillError(f"{args[0]} timed out; outcome may be unknown; no retry") from exc
        try:
            data = json.loads(result.stdout)
        except (ValueError, TypeError) as exc:
            raise DrillError(f"{args[0]} did not return valid JSON; outcome may be unknown") from exc
        if result.returncode:
            raise DrillError(f"{args[0]} failed (exit {result.returncode}): {data}")
        return data


def require(condition, message):
    if not condition:
        raise DrillError(message)


class Drill:
    def __init__(self, client, account, confirm=False):
        self.client = client
        self.account = account.strip()
        self.confirm = confirm
        self.prefix = f"ocal-smoke-{uuid4().hex}-"
        self.created = []
        self.unknown_creates = []
        self.create_requests = {}
        self.delete_attempted = set()
        self.deletion_checks = []
        self.unknown_create_checks = []
        self.window_start = None
        self.window_days = 3
        self.checks = []

    def guard(self):
        require(self.confirm, "Live writes require --confirm")
        require(bool(self.account), "Expected account must not be empty")
        status = self.client.call("status")
        require(isinstance(status, dict) and status.get("connected") is True,
                "Calendar account is not connected")
        actual = status.get("account")
        require(isinstance(actual, str) and actual.casefold() == self.account.casefold(),
                f"Account mismatch: expected {self.account!r}, got {actual!r}")

    def create(self, label, start, end, *extra):
        self.guard()
        subject = self.prefix + label
        # Keep a subject marker if a timeout/error prevents receiving an ID.
        self.unknown_creates.append(subject)
        self.create_requests[subject] = {"start": start, "end": end}
        result = self.client.call("add", subject, start, end,
                                  "--busy", "free", "--force", *extra)
        event_id = result.get("id") if isinstance(result, dict) else None
        require(isinstance(event_id, str) and bool(event_id), "Create response has no event ID")
        self.created.append(event_id)
        self.unknown_creates.remove(subject)
        require(result.get("subject") == subject, "Created event subject differs")
        return event_id

    def check_event(self, event_id, subject, start, end):
        event = self.client.call("read", event_id)
        require(event.get("id") == event_id and event.get("subject") == subject,
                "Read-back identity or subject differs")
        self.check_times(event, start, end)
        return event

    @staticmethod
    def check_times(event, start, end):
        for key, expected in (("start", start), ("end", end)):
            # Graph includes seconds/fractions; compare the same UTC wall minute.
            raw = re.sub(r"(\.\d{6})\d+", r"\1", event[key]["dateTime"]).replace("Z", "+00:00")
            actual = datetime.fromisoformat(raw)  # Also accepts Graph precision on Python 3.10.
            if actual.tzinfo is None:
                require(event[key].get("timeZone") in ("UTC", "Etc/UTC", "GMT", "Etc/GMT"),
                        f"Read-back {key} timezone is not UTC")
                actual = actual.replace(tzinfo=timezone.utc)
            require(actual == datetime.fromisoformat(expected).replace(tzinfo=timezone.utc),
                    f"Read-back {key} differs")

    def window_events(self, subject=None):
        self.guard()
        require(self.window_start is not None, "Test window was not established")
        args = ["list", "--from", self.window_start, "--days", str(self.window_days)]
        if subject is not None:
            args.extend(["--search", subject])
        events = self.client.call(*args)
        require(isinstance(events, list) and all(isinstance(e, dict) for e in events),
                "Test-window query did not return an event list")
        return events

    def exercise(self):
        self.guard()
        context = self.client.call("context")
        require(context.get("timezone") == "UTC" and context.get("utc_offset") == "+00:00",
                "Context did not use UTC")
        today = date.fromisoformat(context["today"])
        calculated = self.client.call("date", "--base", today.isoformat(), "--days", "30")
        day = (today + timedelta(days=30)).isoformat()
        require(calculated.get("date") == day, "Date arithmetic differs")
        self.window_start = day
        self.checks.extend(["context", "date"])

        start, end = f"{day}T14:00", f"{day}T15:00"
        event_id = self.create("timed", start, end)
        self.check_event(event_id, self.prefix + "timed", start, end)
        self.checks.extend(["add", "read"])
        self.guard()
        self.client.call("update", event_id, "--subject", self.prefix + "updated", "--yes")
        self.check_event(event_id, self.prefix + "updated", start, end)
        self.checks.append("update")

        moved = (date.fromisoformat(day) + timedelta(days=1)).isoformat()
        self.guard()
        self.client.call("move", event_id, "--to", moved, "--yes")
        self.check_event(event_id, self.prefix + "updated", f"{moved}T14:00", f"{moved}T15:00")
        self.checks.append("move")
        events = self.client.call("list", "--from", moved, "--days", "1", "--search", self.prefix)
        require(isinstance(events, list) and any(e.get("id") == event_id for e in events),
                "Moved event missing from explicit-date list")
        self.checks.append("list")
        free = self.client.call("free", moved, "--from", "14:00", "--to", "17:00")
        require(isinstance(free, dict) and isinstance(free.get(moved), list),
                "Free-time response lacks the requested date")
        self.checks.append("free")

        pattern = {"type": "daily", "interval": 1}
        series_id = self.create("series", start, end, "--repeat", json.dumps(pattern),
                                "--repeat-times", "2")
        series = self.check_event(series_id, self.prefix + "series", start, end)
        recurrence = series.get("recurrence") or {}
        require(recurrence.get("pattern", {}).get("type") == "daily"
                and recurrence.get("pattern", {}).get("interval") == 1
                and recurrence.get("range", {}).get("numberOfOccurrences") == 2,
                "Recurring event did not retain the requested pattern/range")
        self.checks.append("recurrence")
        instances = [e for e in self.window_events(self.prefix + "series")
                     if e.get("seriesMasterId") == series_id]
        require(len(instances) == 2, "Recurring series did not expand to exactly two occurrences")
        instances.sort(key=lambda e: e["start"]["dateTime"])
        for instance, expected_day in zip(instances, (day, moved)):
            require(instance.get("subject") == self.prefix + "series"
                    and bool(instance.get("id")) and instance["id"] != series_id,
                    "Recurring occurrence identity or subject differs")
            self.check_times(instance, f"{expected_day}T14:00", f"{expected_day}T15:00")
        self.checks.append("recurrence_expansion")

    def cleanup(self):
        errors = []
        for event_id in reversed(self.created[:]):
            if event_id in self.delete_attempted:
                continue
            try:
                # Re-check before every delete; an account change stops cleanup.
                self.guard()
            except Exception as exc:
                errors.append(f"Cleanup stopped: {exc}")
                break
            try:
                # Never repeat a delete because its later read-back failed.
                self.delete_attempted.add(event_id)
                result = self.client.call("delete", event_id, "--yes")
                require(result.get("deleted") == event_id, "Delete response ID differs")
            except Exception as exc:
                errors.append(f"Cleanup could not confirm deletion of {event_id}: {exc}")
        pending = [event_id for event_id in self.created if event_id in self.delete_attempted]
        if pending:
            try:
                events = self.window_events()
                for event_id in pending:
                    matches = [e.get("id") for e in events
                               if e.get("id") == event_id or e.get("seriesMasterId") == event_id]
                    self.deletion_checks.append({"id": event_id,
                                                 "status": "present" if matches else "absent",
                                                 "matching_ids": matches})
                    if matches:
                        errors.append(f"Deleted event or its occurrences remain in test window: {event_id}")
                    else:
                        self.created.remove(event_id)
                if not self.created:
                    self.checks.append("delete_verified")
            except Exception as exc:
                errors.append(f"Cleanup read-back could not confirm absence: {exc}")
                self.deletion_checks.extend({"id": event_id, "status": "unverified"}
                                            for event_id in pending)
        return errors

    def inspect_unknown_creates(self):
        # Observed IDs remain outside self.created: this is a read-only diagnosis.
        for subject in self.unknown_creates:
            result = {"subject": subject, "requested": self.create_requests[subject]}
            try:
                matches = [e for e in self.window_events(subject) if e.get("subject") == subject]
                result.update(status="observed" if matches else "not_found",
                              matches=[{key: e.get(key) for key in
                                        ("id", "seriesMasterId", "subject", "start", "end")}
                                       for e in matches])
            except Exception as exc:
                result.update(status="unverified", error=str(exc))
            self.unknown_create_checks.append(result)

    def run(self):
        errors = []
        try:
            self.exercise()
        except (Exception, KeyboardInterrupt) as exc:
            errors.append(str(exc) or type(exc).__name__)
        finally:
            errors.extend(self.cleanup())
            self.inspect_unknown_creates()
        return {"ok": not errors, "account": self.account, "subject_prefix": self.prefix,
                "checks": self.checks, "errors": errors, "remaining_ids": self.created[:],
                "unknown_create_subjects": self.unknown_creates[:],
                "unknown_create_checks": self.unknown_create_checks,
                "deletion_checks": self.deletion_checks,
                "test_window": {"from": self.window_start, "days": self.window_days, "timezone": "UTC"},
                "cleanup_note": "Only this run's returned create IDs are deleted. "
                                "Inspect remaining IDs or unknown subjects manually; do not rerun blindly."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", required=True, help="Expected connected calendar email")
    parser.add_argument("--confirm", action="store_true", help="Allow test writes and their cleanup")
    parser.add_argument("--lang", choices=["en", "zh"], default="en", help="Calendar CLI language")
    args = parser.parse_args(argv)
    report = Drill(CalendarClient(args.lang), args.account, args.confirm).run()
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
