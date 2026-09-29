# Live Calendar Integration Test

Check that the CLI can create, read, edit, move, and clean up events through Microsoft Graph. One run creates a single event and a two-occurrence series, verifies their changes, deletes the IDs returned by this run, and produces a JSON report.

## Prepare and run

You need Python 3.10+, network access, and a writable Outlook test account. **This workflow changes a real calendar**; use a dedicated test account where possible. Routine offline checks are in the [developer guide](../../DEVELOPMENT.md).

From the project root, use PowerShell to store test credentials separately:

```powershell
python -m pip install requests msal tzdata
New-Item -ItemType Directory -Force .local-calendar-test | Out-Null
$env:OCAL_TOKEN_PATH = Join-Path (Get-Location) '.local-calendar-test/outlook-token.json'
python scripts/outlook_setup.py
python scripts/outlook_cal.py status --json
```

Choose the test account during sign-in. Verify the email returned by `status`, replace `test@example.com` below with that email, and run once:

```powershell
python tests/integration/drill.py --account test@example.com --confirm --lang en > .local-calendar-test/report.json
```

`--account` identifies the expected account and `--confirm` allows test writes and cleanup. The runner checks the account before writes, deletions, and diagnostic queries; mismatches stop that operation. Subprocesses inherit `OCAL_TOKEN_PATH`. Bash credential setup is in [configuration](../../references/configuration.md); the test command is the same.

## Where results go

The command above saves JSON to `.local-calendar-test/report.json` under the project root, overwriting an existing report with that name. Omit redirection to display it in the terminal. Exit code 0 with `ok: true` means both checks and cleanup succeeded.

| Report field | Meaning |
|---|---|
| `ok`, `checks`, `errors` | Overall result, completed checks, and failures. |
| `account`, `subject_prefix`, `test_window` | Target account, unique run prefix, and frozen query dates with UTC timezone. |
| `remaining_ids` | Created IDs whose deletion has not been confirmed. |
| `deletion_checks` | Deletion read-back status: `absent`, `present`, or `unverified`; `target_status` records the original ID read-back and `matching_ids` records surviving related items in the window. |
| `unknown_create_subjects` | Subjects of create requests without a usable returned ID; outcome needs verification. |
| `unknown_create_checks` | Read-only checks of those exact subjects: `observed`, `not_found`, or `unverified`, with matching IDs and times. |

Test events appear temporarily in Outlook with an `ocal-smoke-...-` subject prefix and availability set to free. Dates begin 30 days after the current UTC date; a fixed three-day window covers the two expected occurrence dates and one extra day.

## Inspect a failed run

Cleanup is attempted even after a check fails; automatic deletion is limited to the IDs returned by this run's creates. Uncertain writes remain in the report for inspection. Additional IDs observed by subject queries are diagnostic only. `not_found` describes only the frozen window.

Before rerunning, inspect `remaining_ids` and `unknown_create_checks` in the account and date window named in the report. Forcibly terminating the process can interrupt cleanup; use `subject_prefix` to locate test leftovers and establish their origin and state before acting on them.

## Coverage

The runner checks local `context` and `date` arithmetic, timed-event creation/read/edit/move, `list`, the structure of `free`, and a daily series with exactly two occurrences at the expected times. Cleanup checks delete-response IDs and series flags, then requires both an empty related-item window and an explicit `event_not_found` / 404 when reading the original ID (the master for a series). Other read failures remain unverified. Offline tests cover full input validation, DST, other recurrence patterns, free-slot calculation, and error handling.
