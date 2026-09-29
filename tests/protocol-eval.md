# Output Protocol Evaluation

Check that assistants and scripts extract the correct IDs, times, free intervals, and errors. For example, when a new event conflicts with an existing one, stdout contains the new event result and stderr contains the warning; extraction should yield the new event's ID.

## Run and inspect results

Run offline regressions from the project root; tests mock network and dependency-installation calls:

```bash
python -m pip install pytest requests msal tzdata
python -m pytest tests/test_protocol.py -q
```

The summary appears in the terminal. Add `--junitxml=protocol-results.xml` to save a report in the current directory. To assess assistant extraction, run the cases below with mocked tools in fresh sessions and manually record extracted versus expected values. A suggested location is `.local-calendar-test/protocol-results.md` in a directory you create, separate from automated results.

Prefer decoded `--json` fields. Text anchors and indentation are also part of the current output contract for existing callers.

## Text extraction formats

| Info | Regex | Notes |
|------|-------|-------|
| list 🆔 | `^    🆔 (.+)$` | 4-space indentation |
| add 🆔 | `^   🆔 (.+)$` | 3-space indentation |
| read 🆔 | `^🆔 (.+)$` | flush left |
| Series master event ID | `^🆕 .+?: (.+)$` | anchor+colon structure, flush left; copy before the colon follows the language (zh: 系列主事件ID / en: Series master event ID) |
| free slots | `(\d{2}:\d{2})-(\d{2}:\d{2})` | per-slot HH:MM-HH:MM; no slot list = free all day or no free slots (distinguishing them needs copy or `--json`) |
| --json error | `{"error": ..., "exit": 1}` | stdout can be json.loads'd |

## Output contract

1. **Take event IDs from command results**: JSON `id` / `seriesMasterId`, or the stdout 🆔 / 🆕 lines above
2. **🆔 lines on stdout can only belong to the result event**: non-interactive notices such as conflict warnings (which contain 🆔 lines of existing events) go to stderr
3. Anchors (🆔/🆕/✅/⚠️…) and **structure** (indentation/colons/parentheses/slot formats) are language-independent - identical in zh/en; `--json` field names are language-independent too
4. **Natural-language copy is NOT part of the protocol**: in-line copy (e.g. "系列主事件ID / Series master event ID", "确认? / Confirm?") is translated freely per language; agents extract information from anchors and structure only, never from specific copy
5. In `--json` mode each operation writes exactly one JSON value to stdout; all human-oriented messages go to stderr. `--help` retains text help; `--json` without a command returns a structured argument error. Parameter, command and dependency-startup errors use `{"error": ..., "exit": 1}`; `status` retains its connection-status object when disconnected.
6. Graph/network errors may add language-independent `code`, `http_status`, and `outcome_unknown`; see the [command reference](../references/commands.md). Missing metadata does not imply retry safety.
7. JSON uses ASCII escapes so Unicode event data and error messages survive Windows GBK pipes unchanged after `json.loads`.

## Evaluation cases

For each case, in a fresh session let the agent perform the operation and extract the information, then check the extraction result.

For case 9, `wednesday.json` contains this exact UTF-8 pattern object:

```json
{"type":"weekly","interval":1,"daysOfWeek":["wednesday"],"firstDayOfWeek":"monday"}
```

| # | Operation | Expected extraction |
|---|-----------|--------------------- |
| 1 | `list --from 2026-08-20 --days 7`, output has 3 events | 3 🆔 lines (4-space), one-to-one with the output |
| 2 | `add "Weekly sync" "2026-08-20 15:00" "2026-08-20 16:00"` (conflicts with an existing event) | The new event's 🆔 (3-space line) |
| 3 | `read <occurrence ID>` | Two values: that occurrence's 🆔 + the 🆕 master event ID line (anchor+colon structure) |
| 4 | `free "2026-08-21" --from 09:00 --to 18:00` | List of free slots (HH:MM-HH:MM); no slot list = free all day or no free slots |
| 5 | `delete <ID> -y` on a single event | stdout has a deletion-success line (🗑️ anchor), no leftover IDs |
| 6 | Any operation with `--json` (except text help) | stdout json.loads succeeds directly |
| 7 | `add "bad time" "invalid date"` errors out | ❌ on stderr; stdout empty |
| 8 | English environment (`--lang en`) running cases 1-5 | anchors identical to the Chinese environment |
| 9 | Recurring series: `read` an occurrence → `update <masterID> --repeat-file wednesday.json` with an explicit weekly pattern | master ID from the 🆕 line, not the occurrence ID |
| 10 | `next <series ID>` | the next occurrence's 🆔 (4-space line) |
| 11 | User requests today 14:00–15:00; run `context --json`, then `add` with the resolved absolute start/end and named timezone | Output date matches the context date used to normalize this request; later verification/retries reuse those exact values |
| 12 | `move <occurrence-or-master-ID> --days 1 --json`, in zh/en, including a mocked PATCH failure | Success: one event object with the target ID and shifted dates; failure: one error object. Recurrence warnings stay on stderr in both cases. |
| 13 | `update <ID> --json` without update fields, in zh/en | One `{"error": ..., "exit": 1}` object, process exits 1; no PATCH sent |
| 14 | `--json read` with missing ID, invalid `list --days`, unknown command, or mocked dependency installation failure | One error object, process exits 1; installation diagnostics remain on stderr |
| 15 | `read <ID> --json` through a GBK pipe, with Chinese/emoji event data or a mocked Unicode error, in zh/en | `json.loads` recovers every character exactly; ASCII escapes are expected |
| 16 | Run `read <masterID> --json` in both languages, simulating not-found, authentication, permission, and other 404 failures | Distinguish through `code` and `http_status`; only `event_not_found` / 404 supports target absence. |
| 17 | Create times out in both languages, or simulate a write server error/unparseable success response | One JSON error retains `error`/`exit` and adds `outcome_unknown: true`; create/update is not automatically resubmitted. |

## Assessment

The target is 17/17. Cases 12–15 are also covered offline by `test_protocol.py`. Failure records should include actual stdout, stderr, exit code, and extracted values. Keep tests and this contract aligned when changing output formats.
