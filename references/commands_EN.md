# Command Reference

This is the full command reference for the Outlook Calendar Assistant - a toolkit that manages your Outlook calendar from the command line.
Prerequisites: you have completed sign-in and authorization (see `configuration_EN.md`); every command has the form `python outlook_cal.py <command> [args]`, run from the project's `scripts/` directory.

## Table of Contents

- [General conventions](#general-conventions)
- [1. Viewing your schedule](#1-viewing-your-schedule) (status / list / today / tomorrow / week / read / free / next)
- [2. Adding events: add](#2-adding-events-add)
- [3. Modifying events: update](#3-modifying-events-update)
- [4. Moving events: move](#4-moving-events-move)
- [5. Deleting events: delete](#5-deleting-events-delete)
- [6. Machine-readable output: --json](#6-machine-readable-output---json)

## General conventions

- **Time formats**: timed events use `YYYY-MM-DD HH:MM`, e.g. `2026-08-10 09:00`; all-day events take a date only. **Relative times are also supported**: `today`/`tomorrow`/`day after tomorrow`/`this X`/`next X` (optionally with a time: `today 14:00`, `tomorrow 9:30 am`; Chinese forms like `今天下午2点` work too), resolved against the system clock at run time
- **Event ID**: always taken from the 🆔 line in command output - never fabricated; available from `list` / `add` / `read`
- **--search targeting**: `update` / `delete` / `move` accept `--search "keyword"` instead of an event ID, locating the target by title/location/notes (a unique match operates directly; multiple matches raise an error listing candidate 🆔s; search window: past 7 days ~ next 30 days)
- **Confirmation**: `update` / `delete` / `move` ask for confirmation by default; `-y` skips it; `--json` mode skips it automatically
- **Language**: auto-selected by system language (Chinese system → Chinese, otherwise English); override with `--lang zh|en` (before or after the command) or the `OCAL_LANG` environment variable. `--json` output and emoji anchors are language-independent
- **First run**: missing dependencies (requests/msal/tzdata) are installed automatically; on install failure, manual commands are shown. `tzdata` is essential for correct Windows timezone resolution - without it times may shift
- **Machine-readable**: append `--json` to any command → stdout carries only JSON (see the last section)

---

## 1. Viewing your schedule

### status — connection state
`status`: shows the current account and login expiry.

### list — view events in a time range
Defaults to the next 7 days, grouped by day (time, subject, recurrence mark, category, 🆔).

| Option | Effect |
|--------|--------|
| `--days N` | Look ahead N days (default 7) |
| `--past N` | Also look back N days |
| `--from YYYY-MM-DD` | Start from the given date (ignores `--past`) |
| `--search "term"` | Filter by title/location/notes |
| `--category "name"` | Filter by category |
| `--created-after date` | Only events **added** after this date ("what did I add yesterday") |
| `--reminders` | Only events with reminders set |
| `--summary` | Only daily counts, no details |

```bash
python outlook_cal.py list --days 30 --past 7 --category "Work"
python outlook_cal.py list --from "2026-08-20" --days 5 --summary
python outlook_cal.py list --created-after "2026-08-06" --search "meeting"
```

### today / tomorrow / week — quick views
Today / tomorrow / next 7 days. All support `--search` / `--category` / `--summary`.

### read — event details
`read <ID>`: full information (time, location, category, recurrence rule, importance, privacy, notes, link, created time, organizer). For an occurrence of a recurring series it also shows the series, the Nth occurrence, and the series master event ID.

### free — free time slots
`free [date] [--from HH:MM] [--to HH:MM] [--days N]` (default: today 09:00-18:00, 1 day).
Judged by busy/free status: events marked "free" don't count as occupied; all-day events occupy the whole day.

### next — next occurrence of a recurring event
`next <ID>`: returns the next occurrence within 365 days; a finished series is clearly indicated; non-recurring events raise an error.

---

## 2. Adding events: add

`add <subject> <start> [end]` — omitting the end time defaults to start + 1 hour.

| Option | Effect |
|--------|--------|
| `--all-day` | All-day (start takes a date only) |
| `-l "location"` | Location |
| `-b "notes"` | Notes |
| `--category "Work,Important"` | Categories (comma-separated) |
| `--remind N` | Reminder: all-day = N **days** before; timed = N **minutes** before |
| `--repeat "rule"` | Recurrence (syntax in recurring-events_EN.md) |
| `--repeat-until date` / `--repeat-times N` | Recurrence end condition (requires `--repeat`) |
| `--importance low/normal/high` | Importance |
| `--private` | Private |
| `--busy busy/free/tentative/oof/workingElsewhere` | Busy/free display |
| `--force` | Skip conflict check |

Notes:
- A date without a time is treated as all-day (with a hint)
- All-day events accept a second date for multi-day (e.g. `add "Trip" "2026-08-10" "2026-08-12" --all-day`)
- Overlaps with existing events are warned about, not blocked; `--force` skips the check

```bash
python outlook_cal.py add "Weekly sync" "2026-08-10 09:00" "2026-08-10 10:00" -l "Room 3" -b "Q3 discussion" --category "Work" --remind 10
python outlook_cal.py add "Birthday" "2026-08-15" --all-day
python outlook_cal.py add "Trip" "2026-08-10" "2026-08-12" --all-day
python outlook_cal.py add "Standup" "2026-08-14 10:00" "2026-08-14 10:30" --repeat "every friday" --repeat-times 5
```

---

## 3. Modifying events: update

`update [<ID>] [options]` — only the given fields change, everything else stays; when no ID is given, use `--search` to locate the target.

| Option | Effect |
|--------|--------|
| `--search "term"` | Locate by keyword when no event ID is given (unique match operates directly; multiple matches list candidates) |
| `--subject "new title"` | Change the title (`""` clears it) |
| `--start` / `--end` | Change the time (all-day: date; timed: `date time`) |
| `--all-day` / `--no-all-day` | Convert between all-day ↔ timed |
| `-l` / `-b` | Location / notes (`""` clears) |
| `--category` | Category (`""` clears) |
| `--importance` / `--private`/`--no-private` / `--busy` | Importance / privacy / busy state |
| `--remind N` / `--no-remind` | Set reminder / turn off reminder |
| `--repeat "rule"` / `--repeat ""` | Set recurrence / remove recurrence (back to single) |
| `--repeat-until` / `--repeat-times` | Recurrence end condition (requires `--repeat`) |
| `-y` | Skip confirmation |

Notes:
- Converting to timed without `--end` defaults to start + 1 hour
- All-day events can become multi-day by giving both `--start` and `--end` dates
- Modifying "one occurrence" of a recurring event affects only that occurrence; changing the whole series rule requires the master event (see recurring-events_EN.md)

---

## 4. Moving events: move

`move [<ID>] --days N` or `move [<ID>] --to YYYY-MM-DD` (exactly one); when no ID is given, use `--search` to locate the target.

- **Keeps the original time slot and duration**, only the date changes (same for all-day events)
- `--days` may be negative (move backward)

```bash
python outlook_cal.py move <ID> --days 3          # shift 3 days later
python outlook_cal.py move <ID> --to "2026-08-20" # move to Aug 20
python outlook_cal.py move --search "standup" --to "2026-08-20"  # locate by keyword, then move
```

---

## 5. Deleting events: delete

`delete [<ID>] [-y] [--series]`; when no ID is given, use `--search` to locate the target.

| Option | Effect |
|--------|--------|
| (none) | Confirms first; for an occurrence of a recurring event, asks "delete this occurrence only [1] / the whole series [2]" |
| `--search "term"` | Locate by keyword when no event ID is given (unique match operates directly; multiple matches list candidates) |
| `-y` | Skip confirmation; recurring events default to **this occurrence only** |
| `--series` | Delete the whole recurring series |

---

## 6. Machine-readable output: --json

Append `--json` before or after any command:
- stdout carries only JSON; human-oriented messages go to stderr
- list → array of events; add/read/update → event object; delete → `{"deleted", "subject", "series"}`; free → per-day structure; errors → `{"error", "exit": 1}`
- update/delete/move confirmations are skipped automatically
