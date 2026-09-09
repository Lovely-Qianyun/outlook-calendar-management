# Skill-Level Evaluation Set

Evaluate observable task outcomes after loading the skill. Trigger checks are in `trigger-eval.md`; output checks are in `protocol-eval.md`.

## Method

Use fresh sessions and an isolated mock calendar. Establish that Outlook is the selected calendar. Record commands, returned data, questions, final event state, and the user's report. Compare with and without the skill when measuring its benefit; do not count this document itself as an executed benchmark.

For the dated scenarios, freeze the clock at **2026-09-09 (Wednesday), Asia/Shanghai**. Supply fixtures at query boundaries, including today, tomorrow, and the following day. No live account is required.

## Scenarios

| # | User request / fixture | Pass criteria |
|---|---|---|
| 1 | "What's on tomorrow?" | Uses `context` and explicit date arithmetic as needed, then `list --from 2026-09-10 --days 1`; query runs from September 10 00:00 to September 11 00:00, end excluded; reports matching titles and times, excluding neighboring dates. |
| 2 | "Show this week's meetings", then "Show next week's meetings" | Uses September 7–14 and September 14–21 respectively, with exclusive ends; does not substitute a rolling seven-day window. |
| 3 | "Move the event I added yesterday to today"; event created September 8 but scheduled September 15, 09:00–10:00 | Identifies by creation time, reads details as needed, moves to September 9 09:00–10:00 rather than adding one day, verifies final state, and reports the actual old date. Today-created candidates are excluded. |
| 4 | "Confirmed: delete the September 10 14:00 project meeting, only this occurrence"; fresh full details and occurrence ID already available | Reuses consent without another question, deletes only the occurrence, verifies absence, and leaves the master and other occurrences intact. If target or scope were missing, clarification would be necessary. |
| 5 | "Change the reminder to 10 minutes"; target unambiguous | Verifies the resulting reminder fields, not just title/time; unrelated fields stay unchanged. |
| 6 | Add returns a timeout with an unknown server outcome | Checks for the intended event before resubmitting, avoids duplicate creation, and reports uncertainty if verification fails. |
| 7 | "Add a meeting Friday afternoon"; no other timing context | Resolves the missing start and end/duration before writing; does not silently invent 15:00 or a one-hour duration. |
| 8 | "Am I free this Friday 14:00–17:00?" | Queries September 11 within 14:00–17:00; distinguishes fully free from fully busy through JSON data. |
| 9 | "Every other Wednesday, 09:00–09:30, eight times"; the first date is September 16 | Supplies explicit start/end and a weekly JSON pattern with interval 2, Wednesday, Monday week boundary, and count 8; verifies the returned pattern/range. |
| 10 | Normalization happens at September 9 23:59; an uncertain write is checked after midnight | Retains September 9 and the original named timezone during verification/recovery; does not reinterpret the request as September 10. |
| 11 | A November 1 01:30 event in America/New_York, without specifying which repeated clock time | Resolves the DST ambiguity before writing; uses the intended UTC instant with `--timezone UTC` if necessary, rather than choosing a fold silently. |
| 12 | Change only the start date of a September 11–13 all-day trip to September 12 | Preserves the inclusive September 13 end and all-day type; verifies dates using the mailbox timezone convention. |

## Assessment

Judge the resulting dates, fields, scope, duplicate prevention, and report accuracy. Command names alone or compliance with a fixed number of reads do not establish success. Reusing fresh details and existing authorization is valid.

Pass standard: all 12 scenarios meet their criteria. Record any failures and the actual outputs. Offline command regressions in `test_events.py` and `test_protocol.py` complement this evaluation but do not replace independent agent runs.

After changes to the entrypoint, rerun the relevant scenarios; description changes also require trigger evaluation, and output changes require protocol evaluation.
