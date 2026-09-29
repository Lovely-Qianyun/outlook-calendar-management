# Skill Task Evaluation

Check whether loading the skill leads to the requested calendar outcome. For example, moving an event created yesterday but scheduled next week to today should put the target event on today's date, retain its time slot, and produce an accurate report of the change.

## Prepare and run

Use a skill-capable assistant, fresh sessions, and an isolated mock calendar. Establish Outlook as the selected calendar and load [SKILL.md](../SKILL.md). Freeze dated scenarios at **2026-09-09 (Wednesday), Asia/Shanghai**, with fixtures on the date, neighboring dates, and query boundaries. Use mocked account and tool responses.

Supply each request and fixture below. Record commands, returned data, clarification questions, final event state, and the assistant's reply. Judge observable outcomes. Related offline CLI regressions can be run from the project root:

```bash
python -m pip install pytest requests msal tzdata
python -m pytest tests/test_events.py tests/test_protocol.py -q
```

## Scenarios

| # | User request / fixture | Pass criteria |
|---|---|---|
| 1 | "What's on tomorrow?" | Uses `context` and explicit date arithmetic as needed, then `list --from 2026-09-10 --days 1`; query runs from September 10 00:00 to September 11 00:00, end excluded; reports matching titles and times, excluding neighboring dates. |
| 2 | "Show this week's meetings", then "Show next week's meetings" | Uses September 7–14 and September 14–21 respectively, with exclusive ends; does not substitute a rolling seven-day window. |
| 3 | "Move the event I added yesterday to today"; event created September 8 but scheduled September 15, 09:00–10:00 | Identifies by creation time, reads details as needed, moves to September 9 09:00–10:00 rather than adding one day, verifies final state, and reports the actual old date. Today-created candidates are excluded. |
| 4 | "Confirmed: delete the September 10 14:00 project meeting, only this occurrence"; fresh full details and occurrence ID already available | Reuses consent without another question, deletes only the occurrence, verifies absence, and leaves the master and other occurrences intact. If target or scope were missing, clarification would be necessary. |
| 5 | "Change the reminder to 10 minutes"; target unambiguous | Verifies the resulting reminder fields, not just title/time; unrelated fields stay unchanged. |
| 6 | Add times out; a single attributable candidate exists with the requested fields | Queries the intended date in the retained account/timezone, reads the candidate and verifies all requested fields, reports the verified result, and sends no second create. |
| 7 | "Add a meeting Friday afternoon"; no other timing context | Resolves the missing start and end/duration before writing; does not silently invent 15:00 or a one-hour duration. |
| 8 | "Am I free this Friday 14:00–17:00?" | Queries September 11 within 14:00–17:00; distinguishes fully free from fully busy through JSON data. |
| 9 | "Every other Wednesday, 09:00–09:30, eight times"; the first date is September 16 | Supplies explicit start/end and a weekly JSON pattern with interval 2, Wednesday, Monday week boundary, and count 8; verifies the returned pattern/range. |
| 10 | Normalization happens at September 9 23:59; an uncertain write is checked after midnight | Retains September 9 and the original named timezone during verification/recovery; does not reinterpret the request as September 10. |
| 11 | A November 1 01:30 event in America/New_York, without specifying which repeated clock time | Resolves the DST ambiguity before writing; uses the intended UTC instant with `--timezone UTC` if necessary, rather than choosing a fold silently. |
| 12 | Change only the start date of a September 11–13 all-day trip to September 12 | Preserves the inclusive September 13 end and all-day type; verifies dates using the mailbox timezone convention. |
| 13 | Whole-series deletion returns the correct master ID and `series: true`; the date window is empty but the master still reads successfully | Reads the retained master ID, identifies the surviving series, reports inconsistent acknowledgement/state, and sends no second delete. |
| 14 | Master read-back after series deletion returns explicit `event_not_found` / 404, 401, 403, a network error, or another 404 in separate runs | Confirms absence only for explicit not-found in the correct account/target; other results remain unverified. Retries a transient read at most once and never repeats deletion. Reports mismatched acknowledgement target/scope as inconsistent. |
| 15 | Add times out; queries yield zero candidates, multiple candidates, a partial match, or an indistinguishable pre-existing identical event | Retains the original dates, fields, and account; reports uncertainty and stops automatic creation. An empty window or title match does not settle the outcome. |
| 16 | Reminder update or move times out; reading the retained ID shows all requested fields | Verifies the target and fields, reports the achieved state, and sends no further update/move. |
| 17 | Update/move times out; read-back shows old fields, partial changes, or repeatedly fails | Reports observed values and unresolved verification; does not use an old snapshot or failed read as grounds for another write. |
| 18 | Positive evidence shows the request was never submitted or was rejected before execution; the cause is then resolved | Rechecks the originally authorized target and relevant fields, retries fixed parameters at most once, and uses read-only verification if the retry becomes uncertain. |

## Record results

Pass when all 18 scenarios meet their criteria. A suggested manual session report is `.local-calendar-test/skill-results.md`, including date, assistant version, case number, final fields, pass/fail, and failure evidence. Create the directory if needed; it is ignored by Git. Pytest summaries appear in the terminal and should be recorded separately from session evaluations.

Run affected scenarios after entrypoint changes; use [trigger evaluation](trigger-eval.md) for description changes and [protocol evaluation](protocol-eval.md) for output changes.
