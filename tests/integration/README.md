# Optional live calendar smoke test

`drill.py` exercises the calendar CLI against Microsoft Graph. It creates two uniquely named test events (one is a two-occurrence series), reads and changes them, then deletes only the IDs returned by this run. It never clears the account or deletes events found by a search. Prefer a dedicated test account.

Normal `python -m pytest tests/` runs are offline, including the fake-client checks for this runner. Do not run the live smoke test as part of routine automated verification.

## Run explicitly

Authenticate with the intended test account first. To retain an existing connection, set `OCAL_TOKEN_PATH` to a separate token-file path in the same terminal before both login and testing; see [configuration](../../references/configuration.md). The runner's subprocesses inherit that setting.

```text
python scripts/outlook_setup.py
python tests/integration/drill.py --account test@example.com --confirm
python tests/integration/drill.py --account test@example.com --confirm --lang zh
```

Replace `test@example.com` with the connected calendar account. Both `--account` and `--confirm` are required for writes. The runner checks the live `status --json` account before each write and each cleanup deletion; an account mismatch stops that operation. `--lang` selects the underlying CLI language. The final machine-readable report uses the same JSON fields in either language.

All commands run as Python subprocess argument lists, so Windows does not need Bash. Dates are explicit, timed events have both start and end, recurrence uses JSON, and the timezone is UTC. Test dates start 30 days after the current UTC date. A fixed three-day query window includes the two expected occurrence dates and one extra day to detect excess occurrences. Events are marked free and have a unique `ocal-smoke-...-` subject prefix.

## Coverage and results

The smoke test checks `context`, deterministic `date` arithmetic, timed `add` and `read`, subject `update`, absolute-date `move`, explicit-window `list`, the response structure of `free`, and daily recurring creation. It verifies event read-back values, the series rule, and exactly two expanded occurrences with the requested start/end times. After cleanup, it queries the fixed test window and confirms that the known event IDs and their `seriesMasterId` matches are absent. Detailed validation, DST boundaries, other recurrence patterns, free-slot correctness, and error cases belong to the offline tests.

Exit code 0 and `"ok": true` mean the checks and cleanup succeeded. On failure, the report includes:

- `errors`: failed checks or cleanup operations.
- `remaining_ids`: IDs created by this run whose deletion could not be confirmed.
- `deletion_checks`: read-back status for attempted deletions: `absent`, `present`, or `unverified`.
- `unknown_create_subjects`: unique subjects for create attempts that failed to return a usable ID; their outcome may be unknown.
- `unknown_create_checks`: read-only checks of those exact subjects within the fixed window: `observed`, `not_found`, or `unverified`, with any matching IDs and times. Observed IDs are never added to automatic cleanup.
- `test_window`: the frozen date range and timezone used for these checks.
- `subject_prefix`: the run identifier for manual inspection.

Cleanup runs even after a check fails. It only attempts returned create IDs and rechecks the account before every deletion and diagnostic window query. A timeout, malformed response, or other uncertain write result is not retried by the runner. A failed absence check never causes another deletion attempt. If a create returned no ID, the runner queries its exact subject for diagnosis and reports what it observes without repeating the create or deleting discovered IDs. A `not_found` observation is limited to the frozen window and does not prove the write never happened. Inspect unresolved entries in the expected account before rerunning. Terminating the process forcibly can prevent cleanup; the unique subject prefix helps identify any test leftovers.
