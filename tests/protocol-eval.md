# Output Protocol Evaluation Set

Used to verify that agents and scripts can extract key information from command output **reliably and without errors**. Run through it once before and once after every output-format change, to guard against protocol breakage.

The automated part lives in `tests/test_protocol.py` (the same regexes pinned one by one); this file is the evaluation set for humans/agents, used for end-to-end verification in fresh sessions.

## Extraction regexes (protocol promise - must not change)

| Info | Regex | Notes |
|------|-------|-------|
| list 🆔 | `^    🆔 (.+)$` | 4-space indentation |
| add 🆔 | `^   🆔 (.+)$` | 3-space indentation |
| read 🆔 | `^🆔 (.+)$` | flush left |
| Series master event ID | `^🆕 .+?: (.+)$` | anchor+colon structure, flush left; copy before the colon follows the language (zh: 系列主事件ID / en: Series master event ID) |
| free slots | `(\d{2}:\d{2})-(\d{2}:\d{2})` | per-slot HH:MM-HH:MM; no slot list = free all day or no free slots (distinguishing them needs copy or `--json`) |
| --json error | `{"error": ..., "exit": 1}` | stdout can be json.loads'd |

## Hard rules (violating any of these breaks the protocol)

1. **The 🆔 line is the only source of the event ID** - agents must never guess or fabricate IDs
2. **🆔 lines on stdout can only belong to the result event**: non-interactive notices such as conflict warnings (which contain 🆔 lines of existing events) go to stderr - extracting an ID from stderr is wrong usage
3. Anchors (🆔/🆕/✅/⚠️…) and **structure** (indentation/colons/parentheses/slot formats) are language-independent - identical in zh/en; `--json` output is language-independent too
4. **Natural-language copy is NOT part of the protocol**: in-line copy (e.g. "系列主事件ID / Series master event ID", "确认? / Confirm?") is translated freely per language; agents extract information from anchors and structure only, never from specific copy
5. In `--json` mode stdout is pure JSON; all human-oriented messages go to stderr

## Evaluation cases

For each case, in a fresh session let the agent perform the operation and extract the information, then check the extraction result.

| # | Operation | Expected extraction | Common mistakes |
|---|-----------|---------------------|-----------------|
| 1 | `list --days 7`, output has 3 events | 3 🆔 lines (4-space), one-to-one with the output | grabbing stderr content; mistaking a time for an ID |
| 2 | `add "Weekly sync" "2026-08-20 15:00"` (conflicts with an existing event) | The new event's 🆔 (3-space line) | grabbing the existing event's 🆔 from the conflict warning |
| 3 | `read <occurrence ID>` | Two values: that occurrence's 🆔 + the 🆕 master event ID line (anchor+colon structure) | mistaking the series master ID for the occurrence ID and deleting it |
| 4 | `free "2026-08-21" --from 09:00 --to 18:00` | List of free slots (HH:MM-HH:MM); no slot list = free all day or no free slots | misjudging the no-slot-list form as "has free slots" |
| 5 | `delete <ID> -y` on a single event | stdout has a deletion-success line (🗑️ anchor), no leftover IDs | ignoring the "recoverable" hint line |
| 6 | Any command with `--json` | stdout json.loads succeeds directly | mixing stderr hints into the parse |
| 7 | `add "bad time"` errors out | ❌ on stderr; stdout empty | looking for the error on stdout |
| 8 | English environment (`--lang en`) running cases 1-5 | anchors identical to the Chinese environment | asserting on Chinese copy |
| 9 | Recurring series: `read` an occurrence → `update <masterID> --repeat "every wednesday"` | master ID from the 🆕 line, not the occurrence ID | changing the rule with the occurrence ID (rejected) |
| 10 | `next <series ID>` | the next occurrence's 🆔 (4-space line) | mistaking the "series ended" notice for normal output |
| 11 | `add "Weekly sync" "today 14:00" "today 15:00"` (user said "2 pm today") | the date in the output is the **current date** (cross-check with the "current date" line of `status`), not a date from an earlier session | resolving "today" against old context / yesterday |

Target: 11/11. Any failure means the output protocol is broken - revert the change, or update this file and test_protocol.py in sync.
