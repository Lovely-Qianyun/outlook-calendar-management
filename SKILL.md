---
name: outlook-calendar-management
description: "Use this skill whenever the user mentions any calendar operation on Outlook calendar / Microsoft calendar: view schedules, find events (title/location/category), add meetings/birthdays/reminders, change time or title, move to another date, delete (single occurrence or whole recurring series), check free time slots, query the next occurrence of a recurring event, list recently added events. Manages the Outlook calendar (Microsoft account / outlook.com). Does NOT handle Outlook mail (the himalaya skill does) or other calendars (Google Calendar etc.)."
license: "MIT"
metadata:
  version: 2.2.0
---

# Outlook Calendar Assistant

Manage your Outlook calendar (Microsoft account / outlook.com) through conversation - no need to open the Outlook app. Calendar stays in sync across phone, computer, and web.

## What It Can Do

| What you want | How |
|---|---|
| See your schedule: today/tomorrow/this week/a time range | `today` / `tomorrow` / `week` / `list` |
| Find events: by title/location/notes/category | `list --search` / `list --category` |
| Query "what did I add yesterday" | `list --created-after <date>` |
| Add events: meetings/birthdays/reminders/recurring | `add` |
| Modify events: time/title/category/reminder etc. | `update` |
| Move events: shift by days or to a date, keep the time slot | `move` |
| Delete events; recurring events: single occurrence or whole series | `delete` |
| Ask when someone is free / free time slots | `free` |
| Next occurrence of a recurring event | `next` |
| View an event's details | `read` |
| Calendar unreachable / check status | `status` |
| Machine-readable output for programs/scripts | append `--json` to any command |

> Prefer small output: for "what/when" questions use `list --summary` or `--json` instead of pulling full details; when unsure about the time range, start with the default 7 days.

## Iron Rules

The following rules apply to every operation - never skip them:

1. **Fetch "current time + current timezone" before every operation**: **before any operation begins**, run a command to get the system's current time and timezone - Windows (PowerShell): `Get-Date` + `Get-TimeZone`; Linux/macOS: `date` (e.g. `date +"%F %T %Z"`). **Never use dates or timezones seen in an earlier session.** To cross-check "what day is today", also run `status` (its output includes the current date with year and weekday). Relative time words can be passed to commands directly (`today 14:00`, `this Friday 15:00`); the command resolves them against the system clock at run time and the output shows the resolved date - verify it is not yesterday
2. **Confirm before deleting**: restate the event to delete (title + time) to the user and obtain explicit consent before executing
3. **Read before modifying**: run `read` to get the current content first, then decide what to change
4. **Event IDs come only from output**: the 🆔 line in command output is the event ID - never guess or fabricate
5. **Verify by reading back, then report**: after add/update/move/delete, run `read`/`list` once to verify the actual result (title + time) matches the intent, then report to the user; never claim "done" based only on the command's return value
6. **Don't retry blindly on failure**: when a command exits non-zero, first read the ❌ line (the error field in `--json` mode), then act on the hint - permission/login issues → re-run `python outlook_setup.py`; not found → widen the time range or change the search term; never re-run the exact same command. If still stuck, follow `references/troubleshooting.md` or report honestly to the user

## Output Contract

Command output is the interface between the agent and the scripts - rely on structure only, never on copy:

1. **Extract by anchor + structure**: 🆔/✅/⚠️/🆕 anchors, indentation, `HH:MM-HH:MM` slots, and JSON structure form the language-independent protocol; in-line copy follows the language and is never an extraction basis
2. **Event IDs come only from the 🆔 line** (never guess/fabricate); the recurring series master event ID comes from the 🆕 line (the "🆕 + colon" structure; copy before the colon follows the language)
3. **Failure signals**: exit code 1 + a `❌` line on stderr; in `--json` mode stdout carries `{"error": ..., "exit": 1}`
4. **Always use `--json` for programmatic/batch scenarios**: stdout is pure JSON with no human-oriented text mixed in

## Common Tasks

### "What's my schedule this week / next week?"
→ `week` for this week, `list --days 7` for the next 7 days. Use `list --days 30` for longer; `list --past 30` for the past.

### "That thing I added yesterday - move it to today"
→ ① `list --created-after <yesterday's date>` to find it, note the 🆔 → ② `read` to confirm it's the right one → ③ `move <ID> --days 1` (or `--to today`, keeping the original time slot) → ④ verify by reading back, then tell the user "moved from yesterday X to today X". When the keyword is distinctive enough, do it in one step: `move --search "keyword" --days 1` (a unique match operates directly; multiple matches list candidates).

### "Add a meeting on Friday afternoon with a 10-minute reminder"
→ `add "Meeting name" "this Friday 15:00" "this Friday 16:00" --remind 10`.
"A meeting at 2 pm today" → `add "Meeting name" "today 14:00" "today 15:00"`. Relative time words are resolved by the command against the system's current date; the output shows the concrete date - confirm it's correct. A date without a time is treated as all-day; time conflicts are flagged as a warning, not a blocker, by default.

### "Change the weekly sync to Wednesday"
→ For recurring events, "this occurrence" and "the whole series" are different things: first `read` to get the series master event ID (🆕 line) → `update <masterID> --repeat "every wednesday"`. Note: changing the series rule resets any occurrences that were individually modified before - warn the user first.

### "What time am I free on Friday afternoon?"
→ `free "2026-08-14" --from 09:00 --to 18:00` lists the free time slots.

### "I can't find Friday's meeting"
→ ① `list --search "meeting"` returns nothing - check the search term and time range first (default only covers the next 7 days) → ② widen with `list --days 14` or `--past` → ③ if still nothing, honestly tell the user "not found" and suggest alternatives - **never fabricate events**.

### "Calendar unreachable / permission error"
→ ① run `status` to confirm the connection and login state → ② on invalid_grant/401/403 follow `references/troubleshooting.md` (usually re-run `python outlook_setup.py` to re-authorize) → ③ for network issues, one retry after a moment is fine; if it still fails, report honestly.

## Key Concepts

- **Recurring events** (weekly sync, 15th of every month...): modify/delete on "one occurrence" affects only that occurrence; changing the rule or deleting the whole series must operate on the **master event**. See `references/recurring-events.md`
- **Environment**: Windows / Linux / macOS all supported; `python` in the examples may be `python3` on some systems (e.g. macOS) - use the actual interpreter name
- **Time input**: timed events use `YYYY-MM-DD HH:MM` ("3 pm" = `15:00`); all-day events take a date only; relative times are supported (`today`/`tomorrow`/`this X`/`next X` optionally with a time), resolved by the command against the run-time system clock - **never compute dates yourself** (full conventions in `references/commands.md`). Timezone is handled automatically in the computer's local timezone with cross-timezone conversion; if detection fails, set the `TZ` environment variable (e.g. `TZ=Asia/Shanghai`). All-day events are written in the mailbox's preferred timezone and never span two days even when the machine timezone differs from the mailbox's; this feature needs the `MailboxSettings.Read` permission. The full authorization covers 3 permissions: `Calendars.ReadWrite` (event read/write), `MailboxSettings.Read` (mailbox timezone), `User.Read` (sign-in identity) - **after upgrading, re-run `python outlook_setup.py` once to re-authorize**
- **Confirmation & scripting**: scripts ask for confirmation by default; in agent scenarios use `-y` to skip (in non-interactive environments where input is unavailable, the script auto-cancels)
- **Output language**: auto-selected by system language (Chinese system → Chinese, others → English); override with `--lang zh|en` or the `OCAL_LANG` environment variable. Extraction relies only on the anchors and structure in "Output Contract" - language-independent
- **Auto-install on first run**: missing `requests`/`msal`/`tzdata` are pip-installed automatically on first run. Missing `tzdata` breaks Windows timezone resolution and shifts event times - keep it. On install failure, manual commands are shown; if "dependencies still missing" is reported, restart the terminal

## Output Language
Determine the language of the user's current conversation (look at the current message and recent conversation):
- If the user writes in Chinese (中文), respond in Chinese and pass `--lang zh` on every command.
- Otherwise, respond in English and pass `--lang en`.
Never ask the user which language they want. The script falls back to the system language; your override based on the conversation wins.

## Detailed Reference

| File | When to read |
|---|---|
| `references/commands.md` | Full parameter list and more examples |
| `references/recurring-events.md` | Recurring events (create/modify occurrence/delete series) |
| `references/configuration.md` | First-time connection, switching accounts, bring-your-own Azure app |
| `references/troubleshooting.md` | Errors, failures, unexpected results |
