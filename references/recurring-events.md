# Recurring Events

A recurring event is an event that repeats automatically on a rule, e.g. "a weekly sync every Monday at 9:00" - create it once and it keeps recurring.
This document explains how to modify/delete one **occurrence** of a recurring event versus the whole **series** - the two target different objects and must not be confused.

## Core concept: one occurrence vs. the whole series

A recurring event consists of three parts:

| Concept | What it is | Where you see it |
|---------|------------|------------------|
| **Master event** | The whole series (including the rule) | `read` shows the 🆕 series master event ID line; `list` doesn't show it directly |
| **One occurrence** | A single instance of the series | One line per item in `list`, marked 🔁(series) |
| **An individually modified occurrence** (exception) | One occurrence modified/cancelled on its own | `list` marks 🔁(modified) / 🔁(cancelled) |

**Core rule**: modify/delete/move on "one occurrence" affects only that occurrence; changing the rule or deleting the whole series must operate on the **master event** (the 🆕 series master event ID in `read` output).

## Supported rule syntax (`--repeat "..."`)

| What you want | Write |
|---------------|-------|
| Every day | `every day` (or `every 2 days`, `every N days`) |
| Weekly on a weekday | `every friday` (or `every 2 weeks wednesday`; bare `weekly` starts from the start date) |
| Every weekday | `weekdays` (Monday to Friday) |
| Monthly on a day | `monthly on day 15` |
| Monthly on the Nth weekday | `monthly on the first wednesday` / `monthly on the last friday` |
| Yearly on a date | `yearly on 9/21` |

Chinese syntax is also accepted (`每天`/`每周五`/`每月15日` etc.). End conditions (with `--repeat`):
- `--repeat-until 2026-12-31`: until this date
- `--repeat-times 5`: 5 occurrences in total

## Common operations

| What you want | How |
|---------------|-----|
| Change one occurrence's time (this occurrence only) | `update <occurrenceID> --start ... --end ...` (creates an "exception"; the rest stays) |
| Delete one occurrence (this occurrence only) | `delete <occurrenceID>` → choose [1] this occurrence only |
| Change the whole series rule | `read` to get the 🆕 series master event ID → `update <masterID> --repeat "new rule"` |
| Remove recurrence (back to single) | `update <masterID> --repeat ""` |
| Delete the whole series | `delete <masterID>` (warns) or `delete <occurrenceID> --series` |
| Next occurrence | `next <occurrenceID or masterID>` |
| Shift the whole series by days | `move <masterID> --days N` (warns) |

## Things to watch out for

- **Changing the whole series rule resets** occurrences that were individually modified/deleted before (a warning is shown; warn the user first)
- Moving one occurrence to a time that **overlaps an adjacent occurrence** is rejected ("adjacent occurrence conflict") - the new time must be no earlier than the previous occurrence and no later than the next one
- A deleted occurrence **cannot be accessed again** (reports "does not exist"); re-run `list` to confirm
- Rules the parser can't express produce a **friendly error** instead of silently creating a wrong rule: e.g. `every 3 hours`, `every N weekdays` (unsupported)
