# Trigger Evaluation Set

Used to verify that SKILL.md's description triggers the skill correctly. Run through it once before and once after every description change, to guard against missed triggers and false triggers.

## How to use

For each prompt, ask it verbatim in a **fresh session** and observe whether the agent loads this skill's instructions:

- should-trigger all hit → no missed triggers
- should-not-trigger all miss → no false triggers
- On a missed trigger, check whether context and capability are described clearly
- On a false trigger, check the product and task boundaries

Target: should-trigger 12/12, should-not-trigger 6/6.

For positive prompts that omit the product, first establish in the conversation that the user has selected Outlook calendar. Without a selected product or established context, do not bind generic scheduling requests to Outlook.

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

## Assessing the description

Judge whether the request is an Outlook calendar operation in its actual conversation context, not whether each example word appears in the description. Record observed loads and misses. Revise the capability or boundary only when a failure shows it is unclear; avoid growing keyword and exclusion lists for every example.
