# Recurring Events

Create repeating meetings, birthdays, or reminders, and adjust individual occurrences when needed. For example, “Every Wednesday 09:00–09:30, eight times, starting September 30, 2026” produces one series with eight meetings in Outlook.

## Create a weekly series

Install and sign in using the [quick start](../README.md#quick-start). Create a UTF-8 file named `weekly.json` in the project root:

```json
{"type":"weekly","interval":1,"daysOfWeek":["wednesday"],"firstDayOfWeek":"monday"}
```

These commands write to the real calendar and query the result. Adjust the dates, timezone, title, and count as needed:

```bash
python scripts/outlook_cal.py add "Weekly sync" "2026-09-30 09:00" "2026-09-30 09:30" --repeat-file weekly.json --repeat-times 8 --timezone Asia/Shanghai --json
python scripts/outlook_cal.py list --from 2026-09-30 --days 14 --timezone Asia/Shanghai --json
```

The first command returns the series master, including `id` and `recurrence`. The second expands occurrences in that window. In an otherwise empty calendar, it shows the September 30 and October 7 meetings. `weekly.json` is a local input file; the series is saved in Outlook and JSON results appear in the terminal.

## Choose a pattern and end condition

`--repeat-file` reads the pattern object itself; `--repeat` accepts it inline as JSON. A file reduces shell quoting issues. The six supported types are illustrated below:

| Request | JSON pattern |
|---------|--------------|
| Every 2 days | `{"type":"daily","interval":2}` |
| Every Friday | `{"type":"weekly","interval":1,"daysOfWeek":["friday"],"firstDayOfWeek":"monday"}` |
| Monday and Wednesday every 2 weeks | `{"type":"weekly","interval":2,"daysOfWeek":["monday","wednesday"],"firstDayOfWeek":"monday"}` |
| Monday through Friday | `{"type":"weekly","interval":1,"daysOfWeek":["monday","tuesday","wednesday","thursday","friday"],"firstDayOfWeek":"monday"}` |
| Every 3 months on the 15th | `{"type":"absoluteMonthly","interval":3,"dayOfMonth":15}` |
| Last Friday of each month | `{"type":"relativeMonthly","interval":1,"index":"last","daysOfWeek":["friday"]}` |
| September 21 every year | `{"type":"absoluteYearly","interval":1,"month":9,"dayOfMonth":21}` |
| Last Wednesday of November every year | `{"type":"relativeYearly","interval":1,"month":11,"index":"last","daysOfWeek":["wednesday"]}` |

Each type requires all fields shown in its example:

- `interval` is an integer from 1 to 2,147,483,647; `dayOfMonth` is 1–31; `month` is 1–12. Yearly month/day combinations must be valid, including February 29.
- `daysOfWeek` is a nonempty array of unique lowercase weekdays. Weekly patterns also require `firstDayOfWeek`, from `monday` through `sunday`.
- Relative monthly/yearly `index` is `first`, `second`, `third`, `fourth`, or `last`. Multiple weekday candidates select the earliest matching date in that month, producing one occurrence per month.
- The file directly contains pattern fields, with unique keys belonging to the selected type. Hourly recurrence and intervals counted in working days are outside these patterns' capabilities.

When supplying a pattern, choose one end condition:

| Option | Meaning |
|---|---|
| `--repeat-times 8` | Eight occurrences; counts range from 1 to 2,147,483,647. |
| `--repeat-until 2026-12-31` | Inclusive cutoff date, on or after the start date. |
| Omit both | Continue without an end date. |

## Change one occurrence or the whole series

Scheduled-date `list` queries return expanded occurrences. Use an item's `id` for that occurrence; obtain `seriesMasterId` from `read` to target the series rule. The master's own `id` also identifies the series.

| Task | Command (interpreter and script path omitted) | Conditions and result |
|---|---|---|
| Change one occurrence's time | `update <occurrenceID> --start "2026-10-07 10:00" --end "2026-10-07 10:30" --timezone Asia/Shanghai --json` | Creates an exception; the new time must stay within the allowed adjacent-occurrence boundaries. |
| Delete one occurrence | `delete <occurrenceID> --json` | Deletes that occurrence; verify with `list`. |
| Change the series rule | `update <masterID> --repeat-file weekly.json --repeat-times 8 --json` | Can reset individually modified/deleted occurrences; establish that effect before writing. |
| Remove recurrence | `update <masterID> --repeat= --json` | Keeps a single event with recurrence removed. |
| Delete the series | `delete <masterID> --json` or `delete <occurrenceID> --series --json` | Deletes every occurrence in the series. |
| Find the next occurrence | `next <occurrenceID-or-masterID> --json` | Searches the next 365 days. |
| Shift the series one day | `move <masterID> --days 1 --json` | Targets the whole series. |

**A pattern update rebuilds the end condition.** To retain a cutoff or count, read `recurrence.range` and explicitly pass `--repeat-until` or `--repeat-times`; omitting both makes the series open-ended. `--json` skips terminal confirmation, so establish the target and scope before running it.

After changes, use `read` to verify the pattern, range, and times, and `list` to inspect expanded occurrences when needed. For deletion, match the returned `deleted` ID and `series` flag to the intended scope in the same confirmed account. Verify an occurrence's absence in its date window; for a whole series, also read the retained master ID and require an explicit event-not-found result. An empty window alone does not establish series deletion. Verification errors leave the outcome unresolved; use [uncertain-write recovery](troubleshooting.md#uncertain-writes) before considering any further write.

See the [command reference](commands.md) for formats and [Microsoft Graph recurrencePattern](https://learn.microsoft.com/en-us/graph/api/resources/recurrencepattern?view=graph-rest-1.0) for the pattern model.
