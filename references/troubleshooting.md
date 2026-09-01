# Troubleshooting

This document is for diagnosing command errors (❌ messages or unexpected results). Before troubleshooting, make sure you have completed sign-in and authorization per `configuration.md`; command usage is in `commands.md`.

## Connection / authentication issues

| Symptom | Solution |
| ------- | -------- |
| Device code reports "app not found" | When registering the app, choose account type "Personal Microsoft accounts" and enable "Allow public client flows" (only for bring-your-own-app scenarios) |
| Login expired / invalid_grant | Re-run `python outlook_setup.py` |
| 403 permission error | Confirm the app has the `Calendars.ReadWrite` permission |
| Times are wrong (off by hours) | On Windows run `pip install tzdata`; after installing, re-run the command; if it persists, set the `TZ` environment variable explicitly (e.g. `TZ=Asia/Shanghai`) - it takes priority over system detection |
| All-day events span two days in Outlook | The machine timezone differs from the Outlook account's: re-run `python outlook_setup.py` to grant `MailboxSettings.Read`; afterwards all-day events are written in the mailbox timezone (`status` hints when the two differ) |

## Event operation issues

| Symptom | Solution |
| ------- | -------- |
| "Does not exist" after deleting an occurrence of a recurring event | A deleted occurrence can't be accessed again; re-run `list` to confirm the current state |
| "Adjacent occurrence conflict" when changing an occurrence's time | Adjust to a time no earlier than the previous occurrence and no later than the next one |
| Individually modified occurrences reverted after changing the series rule | This is normal (changing the rule resets exceptions); the script warns before the change |
| No conflict warning when adding | Using `--force` skips the conflict check |
| Can't find events that exist | `list` paginates automatically and doesn't miss events; use `--search` to filter by title/location/notes |

## Input errors (all friendly ❌ messages)

| What you typed | Message |
| -------------- | ------- |
| Wrong time format (`2026/08/10`, `24:00`, `Feb 30`) | Time format error |
| End time earlier than/equal to start | End time must be later than start time |
| Negative reminder / all-day reminder over 1826 days | Reminder can't be negative / all-day reminder supports at most N days |
| Unparseable recurrence rule (e.g. `every 3 hours`) | Can't understand the recurrence rule + list of supported syntax |
| `--repeat-times 0` / end date before start | Repeat count must be ≥ 1 / end date is earlier than start date |
| `--repeat-until`/`--repeat-times` without `--repeat` | Repeat end/count requires --repeat |
| Empty / nonexistent event ID | Event ID required / this event doesn't exist or was deleted |
| `move` with both `--days` and `--to` / moving 0 days | Clearly asks for exactly one / days can't be 0 |

| DST transition day reports "local time doesn't exist" | Normal hint: some wall-clock times (e.g. 02:30 on US Eastern in March) don't exist on transition days; the server may adjust to the post-transition time - use a time that exists |

## When you hit a traceback

Normally all errors start with ❌; if a traceback appears, that's an anomaly - report the script path and the error content to the maintainers.

## Known unsupported features

- Recurrence rules for every N hours / every N weekdays
- Importing .ics files
- Multiple calendars / multiple accounts (planned)
