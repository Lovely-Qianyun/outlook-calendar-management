# Developer Guide

For skill maintainers: code structure, protocol, design decisions, testing approach.
The goal of this document is to let developers understand how the system works without
reading (or reading very little of) the code, and to let the next generation of
developers build directly on this document with an agent - no reverse engineering needed.

## File structure

```
scripts/
  outlook_cal.py        # Entry point: parses CLI args, dispatches to commands; pre-scans --lang so help text renders per language
  outlook_setup.py      # Auth: device-code flow; main() guard - importing doesn't trigger the flow, _box is unit-testable
  ocal_errors.py        # CalError: errors raised to the user
  ocal_bootstrap.py     # First-run dependency self-check and auto-install of requests/msal/tzdata; itself depends only on stdlib
  ocal_i18n.py          # i18n: language resolution + string tables + date/weekday formatting
  ocal_auth.py          # Token retrieval and renewal, using msal
  ocal_time.py          # Timezone detection and time parsing; LOCAL_TZ computed at module load
  ocal_graph.py         # Graph API requests, retries, paging
  ocal_recurrence.py    # Recurrence rules: parsing, formatting, Nth-occurrence computation
  ocal_events.py        # All command implementations, display, conflict/free-time computation

tests/
  conftest.py           # Shared pytest config: scripts dir on sys.path, language state reset
  test_time.py          # Time parsing / timezone / all-day ranges
  test_recurrence.py    # Recurrence-rule parsing / formatting / Nth occurrence
  test_i18n.py          # Language resolution / string-table completeness / date-weekday formatting
  test_events.py        # Pure functions + command paths with mocked network layer
  test_graph.py         # Request retries and error mapping, mocked requests
  test_auth.py          # Token file read/write and renewal, mocked msal
  test_protocol.py      # Output-protocol parsing: pins agent extraction regexes (🆔 indentation / slot format / stdout purity)
  trigger-eval.md       # Trigger evaluation set: verify trigger/no-trigger when changing description
  protocol-eval.md      # Output-protocol evaluation set: 11 end-to-end extraction cases, verified in fresh sessions
  integration/          # Optional: live dry-runs against a real account; needs a dedicated test account, see its README
    drill.sh            # 100 behavior assertions, Chinese output
    drill-en.sh         # Same, English output
    README.md           # Usage and warnings

.github/workflows/
  tests.yml             # CI: offline tests on Linux/Windows/macOS × Python 3.10/3.13

references/             # User documentation
  commands.md           # Full command reference
  recurring-events.md   # Recurring events deep-dive
  configuration.md      # Connection configuration
  troubleshooting.md    # Troubleshooting
  azure-app-setup.md    # Bring-your-own Azure app registration
```

## Prerequisites

- Distribute the whole `scripts/` directory; the entry point and all `ocal_*.py` files must stay together
- Dependencies requests, msal, tzdata usually don't need manual install; first run pip-installs them automatically, see dependency self-check
- On first use, run `python outlook_setup.py` to complete device-code authentication

## Version number rules

`version` is three segments, x.y.z; when each segment increments:

| Segment | When it increments                                                        |
| ------- | ------------------------------------------------------------------------- |
| x       | Breaking changes: command incompatibility, config-format changes, behavior-protocol changes |
| y       | New features or behavior changes: new commands/params, output copy changes, dependency changes |
| z       | Pure maintenance: bug fixes, comment refactors; behavior unchanged        |

## Change conventions

- Before changing output, read the output-protocol section and think about whether downstream parsing would break; zh/en copy is pinned by tests verbatim, so changes require syncing the assertions in both languages and bumping the y version - don't change it casually. Established display habits such as `每周周五` (weekly Friday) stay as-is; don't "fix" them
- After refactoring, run the regression suite (see Testing); offline tests must all pass and, when the protocol changed, the live drill must hit 106/106
- When adding behavior, update the assertions in `tests/` in sync - both language versions; output-format changes must also sync `tests/protocol-eval.md` and `test_protocol.py`

## Dependency self-check

- `ensure_deps()` must be called before `ocal_events` is imported; the full explanation of the import-order constraint is in Key design decisions
- `tzdata` is essential for correct Windows timezones; if missing, the code silently falls back to UTC and times shift by several hours, see the timezone section in Key design decisions
- bootstrap itself may only use stdlib + ocal_i18n; its messages go through t()'s `deps_*` keys

## i18n conventions

- All user-visible text - print / CalError / input prompts - goes through `ocal_i18n.t()`; never hardcode Chinese
- Language priority: `--lang` argument > `OCAL_LANG` environment variable > system-language detection (zh for Chinese systems, en otherwise)
- emoji anchors 🆔/✅/⚠️/🆕 etc. are part of the output protocol: the 🆔 line is the event ID, extracted by both scripts and agents; both languages share the same anchors, never translated; `--json` output is language-independent
- Dates/weekdays use runtime functions like `d_md`/`date_weekday`/`weekday`. The language isn't decided until after module import, so these can't be constants
- New copy must fill both the zh and en tables; a missing key falls back to Chinese, then to the key name, making missed translations obvious during development

## Output protocol: the string protocol

The human-readable output of commands is a stable protocol that agents and scripts parse. The point of the protocol: given any output, you know what each line means and where the ID is without reading the code. Before changing output, check this section and think about whether downstream parsing would break.

### emoji anchors

| Anchor | Meaning | Where it appears |
|--------|---------|------------------|
| 🆔 | Event ID | One line per item in list; result area of add/read |
| 🆕 | Series master event ID | Recurring-series context of read |
| ✅ ⚠️ ❌ ℹ️ | Success / Warning / Error / Info | Command results |
| 🔁 | Recurrence marker | End of list lines; series context of read |
| 📅 🕐 📌 | Date / Time / All-day | Lists and details |
| 📍 🏷️ ⏰ 🔒 📊 📝 🔗 🕘 👤 | Location / Category / Reminder / Private / Busy / Notes / Link / Created time / Organizer | read details |
| 🚫 | User cancelled | Confirmation flow |

### Fixed rules

1. The 🆔 line is the only source of the event ID; agents extract it from there - never guess or fabricate
2. Anchors are language-independent; zh/en output is identical, never translated
3. 🆔 line indentation is stable: 4 spaces in list, 3 in add, flush-left in read. The drill scripts use sed to grab IDs by indentation; changing indentation breaks the regression tests
4. Errors uniformly have a ❌ prefix plus friendly copy, exit code 1; in `--json` mode output `{"error": ..., "exit": 1}`
5. The confirmation prompt is fixed: `确认? [y/N]`, accepting y/yes; delete's series choice accepts `2`/`系列` (series)/`s`/`series`
6. In `--json` mode, stdout outputs only JSON; all human-oriented messages go to stderr. In non-`--json` mode, **non-interactive notices/warnings** (conflict warnings, auto-all-day hint, recurrence-removed/reset warnings, nothing-to-update notice) also go to stderr - stdout only carries results, 🆔 protocol lines, and the interactive confirmation dialog. Conflict warnings contain 🆔 lines of existing events; if they leaked into stdout, an agent could mistake one for the new event's ID

### Line structure

- Each list item takes two lines: `    {图标} {时间}  {标题}{定期标记}{类别}` (icon / time / subject / recurrence mark / category), followed by `    🆔 {ID}`
- The recurrence mark is 🔁 plus a parenthesized suffix: `(系列)` (series) / `(已修改)` (modified) / `(已取消)` (cancelled); the series master line additionally ends with the rule description
- read's ID line: `🆔 {ID}`; series context: `🆕 系列主事件ID: {ID}` (series master event ID: {ID})
- Each free line: `📅 {日期} {星期}：{时段列表} 空闲` (date / weekday: free slots), slots formatted HH:MM-HH:MM

### Time and dates

- Time is always MM/DD HH:MM; the numeric format is identical in both languages
- Date: `08月10日` (Aug 10) / `08/10`; weekday: `周一` (Mon) / `Mon`; all-day: `全天` (all day) / `All day`; date range: `~` / `-`
- Recurrence descriptions: `每天` (every day) / `每N天` (every N days) / `每周X` (weekly on X) / `每N周X` (every N weeks on X) / `每月N日` (monthly on day N) / `每月第N个周X` (monthly on the Nth X) / `每年X月X日` (yearly on M/D); end-condition suffixes: `（共N次）` (N total) / `（至日期）` (until a date)

## Testing

### Unit tests: the main entry point for daily development

Runs offline with all network calls mocked; CI-ready:

```bash
python -m pytest tests/          # requires pytest
python -m py_compile scripts/*.py
```

Coverage: time-parsing edge cases, all recurrence-rule forms and invalid inputs, i18n string-table completeness (every key used by t() calls in the scripts must exist in both the zh and en tables), conflict/free-time computation, Graph retries and error mapping, token renewal and its cross-process lock, mailbox-timezone fallback, DST-transition detection, output-protocol parsing (test_protocol.py), and all command paths with the network mocked.

CI: `.github/workflows/tests.yml` runs the same offline suite on Linux/Windows/macOS × Python 3.10/3.13 - the timezone-detection chain, cross-platform paths, and encoding degradation rely on it.

Note: `outlook_setup.py`'s main() is guarded; importing it does not trigger the device-code flow. That flow is a network poll - don't mistake it for an infinite loop.

### Trigger evaluation: for description changes

The description decides when the skill triggers; before changing it, run through `tests/trigger-eval.md` once: 12 requests that should trigger and 6 that shouldn't, verified one by one in fresh sessions. Missed triggers - add keywords; false triggers - add exclusion conditions. Target: 12/12 and 6/6.

### Protocol evaluation: for output-format changes

Output format is the contract agents and scripts parse; before changing it, run through `tests/protocol-eval.md`: 11 end-to-end extraction cases (🆔 / free slots / error shape), verified one by one in fresh sessions. The same regexes are pinned automatically by `test_protocol.py`. Target: 11/11.

### Live integration drill: optional

Unit tests cannot verify real Graph behavior; two 106-assertion scripts in `tests/integration/` cover that. **You must use a dedicated test account** - the baseline cleanup at the start of the scripts deletes events in a ±400-day window, so never point them at your personal calendar. See `tests/integration/README.md` for usage.

> ⚠️ **Agent notice**: before running drill.sh / drill-en.sh, you MUST explicitly warn the user that the script **permanently deletes ALL events and ALL recurring series masters in a ±400-day window** (irrecoverable), and obtain explicit consent before executing. Test accounts only. The scripts have a double guard: they require a `confirm` argument, AND the specified test-account email must match the currently connected account (verified live via `status`); otherwise they refuse to run.

```bash
python outlook_setup.py   # authenticate with the test account first
bash tests/integration/drill.sh confirm <test-account-email>
```

Pass criterion: 106/106. When adding behavior, update the assertions in sync - both the Chinese and English scripts.

## Key design decisions

The decisions below are scattered throughout the code; without this note they are hard to spot. Read them before changing anything. Each one is a conclusion from a pitfall or a careful trade-off - don't change them casually.

### Request layer

1. **All requests carry the immutable-ID header**. `Prefer: IdType="ImmutableId"` - event IDs stay unchanged when events move across containers, keeping delete/update stable
2. **Never retry POST/PATCH**. The server may have already processed the request; resending creates duplicate data. On network errors, tell the user to run list first to confirm, rather than blindly resending
3. **429 waits per Retry-After**; only when the header is missing use 1/2/4-second backoff. 500/503 are retried only for GET/DELETE
19. **The timezone-header 400 fallback goes back through the main loop**. Some mailboxes reject the outlook.timezone header with a 400: strip the header, `continue` the main loop (same retry and error mapping for 429/500/network errors), strip only once; a second 400 is reported as a normal API error

### Graph semantics

4. **Graph convention for all-day events**. start is fixed at 00:00:00, end is the last day's next-day 00:00 (exclusive); `_all_day_range` converts it back to an inclusive date span
5. **Query parameters carry the local offset**. `isoformat` naturally includes offsets like +08:00, so Graph doesn't interpret the times as UTC; otherwise events between 0:00-8:00 daily would be missed
6. **Use `isReminderOn: false` to clear reminders**. Graph ignores a null PATCH on reminderMinutesBeforeStart, and the null + isReminderOn combination returns 500
7. **--created-after uses the events endpoint**. calendarView doesn't support createdDateTime filtering
8. **Exception semantics of recurring series**. PATCH/DELETE on an occurrence automatically creates an exception affecting only that occurrence; changing the rule or deleting the whole series must operate on the master event
9. **/instances gets no $top/$orderby**. The endpoint has a history of errors on these parameters and returns results in ascending start order by default; `next` truncates locally to the nearest occurrence
10. **free is computed locally**. getSchedule is unavailable for personal accounts

### Computation semantics

11. **Conflict-detection window**. Timed events expand 1 hour before and after; all-day events check the **entire date span** (multi-day all-day events check every day, not just the first); calendarView returns every occurrence in the window, so each occurrence of a series that falls in the window is checked at its actual time
12. **showAs=free doesn't count as occupied**. Both conflict detection and free-time computation follow this; **cancelled occurrences (isCancelled) don't count either** - calendarView returns them, and skipping them avoids false conflicts / false busy time

### Timezone and loading

13. **Timezone detection chain** (_detect_local_tz, first success wins): TZ env var → Windows registry → system tzinfo key → /etc/timezone → /etc/localtime symlink → /etc/localtime content match against tzdata → derive Etc/GMT±N from the current offset (warn once) → UTC (warn). The fallback must never silently label naive local times as UTC - that shifts every newly created event. If TZ is an unparseable POSIX rule string (CST-8 etc.), a sentinel routes straight to the offset fallback: once TZ is set it's the authoritative config, so never fall back to reading a different timezone config under /etc
13b. **Full CLDR windowsZones mapping**. There are ~140 official Windows timezone names; the table must be complete, not curated - one missing entry silently displays a whole region's events as UTC (off by hours). Deprecated XP-era names live in LEGACY_WINDOWS_TZ_MAP, used for parsing only, never for the reverse lookup
13c. **_normalize_dt keeps the timezone suffix when truncating 7-digit fractions** (+08:00/Z); otherwise timestamps with offsets get reinterpreted as naive and shift by hours
14. **LOCAL_TZ is computed at module load**. ocal_time probes the local timezone at import and reuses it globally afterwards - no further probing
15. **Import-order constraint**. `ensure_deps()` must run before `ocal_events` is imported; with missing dependencies a top-level import would crash first, so outlook_cal puts its imports inside main()

### Command conventions

16. **cmd_* return semantics**. 0 = success, 1 = failure or user cancellation
17. **today/tomorrow/week reuse cmd_list**. They mutate args in place with setattr and call it - no duplicated logic
18. **For all-day reminders, N is "days"**; for timed reminders, N is "minutes". Cap: 1826 days = 2629800 minutes. In update, judge by the **resulting** type - `--no-all-day --remind N` must treat N as minutes
20. **Multi-day all-day events**. add/update take an end date to span multiple days (inclusive; Graph's end stores the day after the last day at 00:00). An end with a time in the all-day branch is an error - never silently truncate to one day
21. **Emoji output degrades instead of crashing on narrow-encoding pipes**. Printing emoji into a Windows GBK pipe raises UnicodeEncodeError; harden_stdio() in main() switches errors to replace (UTF-8 terminals unaffected, --json output not involved)
22. **All-day events are written in the mailbox's preferred timezone**. When the computer's timezone differs from the mailbox's, all-day events written in the computer's timezone span two days in Outlook. setup now requests MailboxSettings.Read; once per process we read /me/mailboxSettings timeZone. **Old tokens without this permission silently fall back to the local timezone** (same behavior as before), but users should re-run setup; status shows a hint line when the two differ
23. **Token renewal takes a cross-process lock**. Before refreshing, take a lock (fcntl/msvcrt, non-blocking - skip if unavailable) and double-check the token file: two terminals refreshing concurrently won't duplicate requests or interleave file writes; if the lock is skipped, both refresh tokens remain valid and last-writer-wins, so correctness is unaffected
24. **Deletion hints recoverability**. Graph deletions land in Outlook's Deleted Items and stay recoverable for a while; a hint line follows the delete success message
25. **Nonexistent DST times get a warning**. _local_time_exists detects skipped wall-clock times via an aware→UTC→local roundtrip; add/update/move warn on stderr without blocking (ambiguous times don't warn - fold=0 is self-consistent)
26. **--remind must also turn isReminderOn on**. PATCHing only the minutes does not re-enable the reminder switch (after a previous --no-remind, a newly set reminder would silently never fire)
27. **Protocol tests are double-pinned**. test_protocol.py pins the agent extraction regexes (🆔 indentation / stdout purity) automatically; protocol-eval.md is the human/agent end-to-end evaluation set (11 cases). Changing output format requires syncing both
28. **Relative times are resolved by the command at run time**. 今天/明天/后天/本周X/下周X (zh/en, optionally with 24-hour or Chinese times like 今天下午2点) are accepted as time arguments; _parse_dt_arg resolves them against the system clock (now is injectable for tests). Resolution never depends on agent context, so "today" can never become yesterday. status prints the current date (--json has a today key) for agents to cross-check

## Reference: official Graph API docs

| Topic | Link |
| ----- | ---- |
| API overview | https://learn.microsoft.com/en-us/graph/api/overview?view=graph-rest-1.0 |
| event resource | https://learn.microsoft.com/en-us/graph/api/resources/event?view=graph-rest-1.0 |
| Create event | https://learn.microsoft.com/en-us/graph/api/user-post-events?view=graph-rest-1.0 |
| calendarView | https://learn.microsoft.com/en-us/graph/api/calendar-list-calendarview?view=graph-rest-1.0 |
| Recurrence pattern / range | https://learn.microsoft.com/en-us/graph/api/resources/recurrencepattern?view=graph-rest-1.0<br>https://learn.microsoft.com/en-us/graph/api/resources/recurrencerange?view=graph-rest-1.0 |
| List instances | https://learn.microsoft.com/en-us/graph/api/event-list-instances?view=graph-rest-1.0 |
| Query parameters: paging/filter/select | https://learn.microsoft.com/en-us/graph/query-parameters |
| Error handling | https://learn.microsoft.com/en-us/graph/errors |
| Throttling | https://learn.microsoft.com/en-us/graph/throttling |
| Timezone dateTimeTimeZone | https://learn.microsoft.com/en-us/graph/api/resources/datetimetimezone?view=graph-rest-1.0 |
| Device-code flow (MSAL) | https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-device-code |
