# Live Integration Drill (optional)

drill.sh / drill-en.sh are 106 behavior assertions against the real Microsoft Graph, covering what unit tests cannot verify.

## ⚠️ Destructive warning (agents must read)

> **Any agent (AI assistant) MUST clearly explain the following consequences to the user and obtain the user's explicit consent before running drill.sh / drill-en.sh:**
>
> ① The "baseline cleanup" at the start of the scripts **deletes ALL events in a ±400-day window**, including **ALL recurring series masters** - this is **permanent, irrecoverable deletion**, with no recycle bin
> ② If the currently authenticated account is your personal real calendar, **all your personal events will be gone** after the run
> ③ The scripts may only run against a **dedicated test account**; pointing them at a real account causes a serious incident
> ④ The scripts have a **double safeguard**: ① the `confirm` argument must be explicitly passed; ② the test-account email must be specified and match the currently connected account (verified live via `status`) - on mismatch they refuse to run

## Warnings

- **You must use a dedicated test account**. The baseline cleanup at the start of the scripts deletes all events in a ±400-day window and all recurring series masters; pointing them at your personal real calendar causes an incident
- The scripts really write and delete events; leftover test data in the calendar after the drill is normal
- Requires network access and cannot run in CI; for daily development, `python -m pytest tests/` is the norm

## Usage

```bash
python outlook_setup.py   # authenticate with the test account first; token stored at ~/.outlook_cal_token.json
bash tests/integration/drill.sh confirm zrancalendar@outlook.com     # Chinese-output version (2nd argument = test account)
bash tests/integration/drill-en.sh confirm zrancalendar@outlook.com  # English-output version (OCAL_LANG=en)
# or: TEST_ACCOUNT=zrancalendar@outlook.com bash tests/integration/drill.sh confirm
```

Account check: the script runs `--json status` first at startup; when the currently connected account differs from the specified test account (including not connected), it refuses to perform any deletion. This is a machine-level guard on top of `confirm` - even if a real account's token were misused, no real events would be deleted.

The 106 assertions of the two scripts correspond one-to-one; only the expected copy differs. Pass criterion: 106/106.

## Coverage (106 items)

| Group | Content | Items |
|-------|---------|-------|
| 0. Account guard + baseline cleanup | Account-consistency check; deletes series masters before single events (_get_all paging); window empty after cleanup | 1 |
| 1. Time-parsing edges | Zero-padding/omission leniency, out-of-range and natural-language errors, end<start | 11 |
| 2. remind edges | 0/negative/all-day over cap | 3 |
| 3. Recurrence-rule edges | All rule forms + invalid input | 12 |
| 4. Conflict-detection edges | Overlap/touching/free/all-day | 5 |
| 5. update edges | Empty fields/clearing/time validation/all-day-conversion error | 8 |
| 6. Deletion edges | Nonexistent ID, EOF cancel | 2 |
| 7. Recurring-series depth | Nth occurrence/exception/next/delete occurrence/delete series | 9 |
| 8. free/command edges | Invalid windows/normal output/multi-day | 6 |
| 9. --json edges | Pure JSON/structured errors/stderr | 4 |
| 10. Other edges | emoji/long notes/multiple categories/importance | 5 |
| 11. move special | --days/--to/0 days/argument conflict/all-day/series warning/cross-boundary error | 9 |
| 12. Multi-day all-day / quick commands / filters | add+update multi-day all-day, multi-day all-day 2nd-day conflict warning, today/tomorrow/week, --created-after+--reminders, private/importance display | 12 |
| 13. v1.2.0 behavior regression | Timed-reminder minute semantics, cancelled occurrence doesn't occupy free time, delete-occurrence copy, remove recurrence | 5 |
| 14. TZ env var override | Real Graph queries under TZ=Asia/Hong_Kong, TZ=America/Phoenix (official Windows name mapping + Prefer header accepted) | 2 |
| 15. DST transition day (TZ=America/New_York) | Event creation and read-back on fall-back day, warning for nonexistent time on spring-forward day, free/list across DST | 5 |
| 16. Mailbox timezone alignment | status hints mailbox/local timezones differ; all-day events written in the mailbox's preferred timezone (local timezone overridden by TZ to US Eastern) | 2 |
| 17. Relative times | add with "today/tomorrow" relative times; created events land on the correct dates | 4 |
