# Skill-Level Evaluation Set

Evaluates the **actual quality of operations** once the agent has loaded this skill, rather than merely verifying whether it triggers (trigger verification is in `trigger-eval.md`, output-protocol verification in `protocol-eval.md`).

Following the skill design recommendations of Anthropic / OpenAI: triggering successfully ≠ operating as intended; a with/without baseline comparison is needed in fresh sessions.

## How to use

For each scenario, ask it verbatim in a **fresh session**, record the behavior with and without the skill respectively, and check against the pass criteria:

- **Command invocation**: whether it called the `outlook_cal.py` CLI (rather than guessing)
- **Argument correctness**: whether time arguments are resolved at run time (not dates from an earlier session)
- **Iron-rule compliance**: whether it confirms before deleting, reads before modifying, and verifies by reading back after operations
- **Failure handling**: whether on errors it reads the ❌ line and acts accordingly (no blind retries)

## Evaluation scenarios

| # | User request | Pass criteria (all must hold) |
|---|--------------|-------------------------------|
| 1 | "What's on my schedule tomorrow?" | ① called one of `today`/`list`/`week`; ② the command output contains the resolved current date (not an earlier session's date); ③ the report gives event titles + times, not just "queried" |
| 2 | "Move Friday's meeting to next week" | ① locate first with `list`/`search` (get the 🆔), then `move`; ② restate the target event to the user or confirm by reading back before moving; ③ read back after `move` to verify the new date; ④ no fabricated IDs |
| 3 | "Delete tomorrow afternoon's meeting" | ① restate the event (title + time) to the user and obtain consent before deleting; ② use the 🆔 from the output; ③ read back / report the actual result after deleting; ④ if the command fails, act on the ❌ line instead of retrying verbatim |

## Judgment criteria

- with/without baseline: without the skill, an agent may fabricate commands or ask the user to operate manually; with the skill, it should consistently follow the CLI flow
- Iron rule 1 (fetch current time and timezone): in scenario 1, if the agent resolves "tomorrow" using a date from an earlier session, it's an immediate fail
- Pass standard: all 3/3 scenarios must fully meet their criteria

## Change checklist

After modifying SKILL.md (iron rules, common tasks, output contract), re-run this evaluation set; protocol-layer changes (output format) run `protocol-eval.md`; trigger-description changes run `trigger-eval.md`.
