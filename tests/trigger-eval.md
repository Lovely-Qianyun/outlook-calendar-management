# Trigger Evaluation

Check whether the assistant loads this skill for Outlook calendar tasks. For example, “What's on tomorrow?” in a conversation that has selected Outlook should load it; “Write an email” should not.

## Run the evaluation

Use a skill-capable assistant with the complete project installed. Enter each prompt verbatim in a fresh session and observe whether it loads [SKILL.md](../SKILL.md). Use mocked tools when evaluating activation alone to avoid calendar writes.

For positive prompts that omit the product, first establish that the user has selected Outlook calendar. Record the expected and observed activation with session evidence. Run before and after description changes to compare routing behavior.

## should-trigger

| # | User request | Capability |
|---|--------------|------------|
| 1 | What's on my schedule tomorrow? | View schedule |
| 2 | What meetings do I have this week? | View schedule |
| 3 | Do I have anything on the 15th of next month? | View a time range |
| 4 | Add a meeting for Friday at 3 pm | Add event |
| 5 | The event I added yesterday - move it to today | Find by created date + move |
| 6 | Change the weekly sync to Wednesday | Change recurrence rule |
| 7 | Delete the dinner gathering the day after tomorrow | Delete event |
| 8 | Am I free Friday afternoon from 2 to 5? | Free time slots |
| 9 | When is the next standup? | Next occurrence of a recurring event |
| 10 | What events did I add recently? | Query by created date |
| 11 | Search the calendar for "birthday" | Find by title |
| 12 | The Outlook calendar won't connect - check the status | Status check |

## should-not-trigger

| # | User request | Why it shouldn't trigger |
|---|--------------|--------------------------|
| 1 | Write an email to my boss | Email is outside this skill |
| 2 | Check my inbox | Email |
| 3 | Add a reminder in Google Calendar | Other calendar |
| 4 | Check the weekend on Apple Calendar | Other calendar |
| 5 | What is Outlook? | Pure knowledge question, no calendar operations |
| 6 | How many workdays are there in 2026? | Unrelated to calendar operations |

## Record results

The target is all 12 positive prompts loading the skill and all six negative prompts leaving it unloaded. A suggested manual report is `.local-calendar-test/trigger-results.md`, with date, assistant version, case number, observed activation, and failure evidence. Create the directory if needed; it is ignored by Git. This is a session-based evaluation with a manually written report.

For misses or false positives, inspect the capability and scope description in the actual conversation context, then rerun affected cases.
