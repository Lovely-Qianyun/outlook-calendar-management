---
name: outlook-calendar-management
description: "View, find, add, update, move, and delete Outlook / Microsoft calendar events, including recurring events and free-time queries. Use when the user names Outlook calendar or the conversation already establishes it as the calendar to manage. Does not handle email or other calendar products."
license: "MIT"
metadata:
  version: 3.0.0
---

# Outlook Calendar Management

Manage the connected account's default Outlook calendar: queries, creation, edits, moves, deletion, recurring events, and free-time searches. Resolve the user's request in context, then call the bundled Python CLI with explicit parameters.

## Requests and expected results

Assume the current date is **2026-09-28 in Asia/Shanghai**:

| Request | Operation | Verify and report |
|---|---|---|
| “What's on tomorrow?” | Query `list --from 2026-09-29 --days 1 --json`. | That date's event titles and times. |
| “Add a half-hour meeting this Friday at 15:00, with a 10-minute reminder.” | Add four days to Monday to get October 2; create 15:00–15:30 with `--remind 10`. | The new event's date, times, and reminder. |
| “Move the planning event I added yesterday to today.” | Find it by creation date, then `move <ID> --to 2026-09-28 --json`. | Its previous and new scheduled dates, with the time slot preserved. |
| “Am I free this Friday 14:00–17:00?” | Query `free 2026-10-02 --from 14:00 --to 17:00 --json`. | The returned available intervals. |

Calculate actual dates from current context; also pass the resolved `--timezone` to these commands.

## Run the CLI

Resolve paths relative to this skill directory and use Python 3.10+:

```bash
python "<skill-directory>/scripts/outlook_cal.py" context --timezone Asia/Shanghai --json --lang en
```

The following examples omit the interpreter and script prefix. Prefer `--json` and read decoded fields. Use `--lang zh` for Chinese conversations and `--lang en` otherwise; reply in the user's language. These options and `--timezone` work before or after the command.

For first connection or account changes, follow [configuration](references/configuration.md), run `scripts/outlook_setup.py`, and check the account with `status --json`. Calendar commands need network access and sign-in; missing requests, msal, and tzdata are installed automatically. Local `context` and `date` work without sign-in; regional timezones need system timezone data or installed tzdata.

## 1. Resolve dates, target, and scope

- Relative dates require a current clock and effective timezone. When that context is missing or stale, call `context --json`, adding `--timezone` for a user-specified zone. It returns `now`, `today`, `timezone`, `utc_offset`, `weekday`, and Monday's `week_start`.
- Calculate dates with `date --base YYYY-MM-DD --days N --json` or Python date arithmetic. This Friday is `week_start` plus four days. Reuse the same named timezone in subsequent commands.
- CLI dates are zero-padded `YYYY-MM-DD`; timed values are `YYYY-MM-DD HH:MM` or `YYYY-MM-DDTHH:MM`, with timezone supplied separately. Timed creation requires start and end; all-day creation uses `--all-day`. Resolve missing bounds, duration, or all-day intent from context or necessary clarification before writing.
- Use result `id` / `seriesMasterId` values. Before edits or deletion, confirm relevant existing fields through `read` or fresh complete results; resolve multiple candidates and occurrence versus series scope. Existing authorization for the identified action and scope remains valid.
- Retain the connected account, target, scope, absolute dates/times, timezone, and requested fields before writing, and reuse them during verification and recovery.

## 2. Carry out the operation

| Task | Command |
|---|---|
| Query scheduled dates | `list --from YYYY-MM-DD --days N --json` |
| Filter that result | Add `--search "term"`, `--category "name"`, or `--reminders` |
| Find by creation date | `list --created-after YYYY-MM-DD --created-before YYYY-MM-DD --json` |
| Details / next occurrence | `read <ID>` / `next <ID>` |
| Create / edit / move / delete | `add` / `update` / `move` / `delete` |
| Free time | `free YYYY-MM-DD --from HH:MM --to HH:MM --json` |

A scheduled-date query spans N calendar dates, ending at the exclusive midnight after the final date. Creation filters also exclude their `--created-before` boundary. For an unspecified query range, an initial seven days from `context.today` is reasonable; state that range in the report. Use normal lists for titles and times; `--summary` returns daily counts only.

Timed operations use the selected timezone. All-day writes use the mailbox timezone when available, otherwise the selected timezone. All-day end dates are inclusive; converting between timed and all-day events requires both new bounds.

For recurring operations, read [recurring events](references/recurring-events.md). Supply a Graph pattern JSON file; target the master for rule changes and explicitly supply the end condition to retain an existing cutoff or count. Series rule changes can reset individually changed or deleted occurrences; explain that effect before the operation.

`--json` and applicable commands' `-y` skip terminal confirmation; establish the requested target and scope before executing. The `--search` shortcut covers the past seven through the next thirty days. For other windows, use `list` and then pass the ID.

## 3. Verify and deliver the result

After creation, update, or move, read back once and verify the requested fields. Verify deletion in the same confirmed account, using the retained target and scope:

- Check a successful delete response's `deleted` ID and `series` flag against the intended target: the occurrence ID for one occurrence, or the master ID for the whole series. A mismatch needs investigation before further writes.
- For a single event or occurrence, query its scheduled date window and check the target ID's absence. For a whole series, also `read` the retained master ID and require an error with `code: event_not_found` and `http_status: 404`. An empty window alone does not establish series deletion; authentication, permission, or network errors leave verification unresolved.
- A failed verification does not authorize another delete. For an uncertain delete without a success response, use the retained target and scope with the same read-only checks and report only what they establish.

For a timeout or uncertain write, inspect the retained ID, or locate creation candidates in the intended date window and compare the requested fields. A uniquely attributable match with the expected fields establishes the requested result; stop writing. Zero matches, multiple candidates, partial matches, or failed reads leave the outcome uncertain. Stop automatic writes and explain what is known. Retry only with positive evidence that the request was never submitted or was rejected before execution, after resolving the cause and rechecking the authorized target; reuse the fixed parameters and allow one agent-level retry. Recovery details are in [troubleshooting](references/troubleshooting.md#uncertain-writes). Retry a transient read once; if it still fails, report what could not be verified.

Report the actual outcome, including relevant before/after values for changes and any unresolved verification. Calendar changes are saved in Outlook; query results appear in the reply. Save JSON to a user-specified location when a file is requested.

In JSON operation mode stdout is one JSON value and diagnostics go to stderr. Check the exit code and error fields `error` and `exit`, plus `code` and `http_status` when available. `outcome_unknown: true` marks an uncertain write; its absence does not establish retry safety; disconnected `status` returns `connected: false`. Free-time JSON lists intervals by date: an empty array means no free time in the queried window, and the full interval means entirely free.

Full parameters, output structures, and examples are in the [command reference](references/commands.md).
