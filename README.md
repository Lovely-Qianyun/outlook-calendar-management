🌐 English | [中文](README.zh-CN.md)

<p align="center">
  <img src="./icon/appIcon.png" alt="Outlook Calendar Management logo" width="20%">
</p>

# Outlook Calendar Management

Manage your Outlook calendar by talking to an AI assistant, or run calendar commands directly from a terminal. View upcoming plans, find time for a meeting, reschedule an event, and maintain recurring reminders in the connected account's default calendar.

Supports personal Outlook.com and Microsoft 365 accounts, with English and Chinese output. The project includes an agent skill and a local Python command-line tool that connects to Microsoft Graph.

## What you can do

| Your request | What happens | Result |
|---|---|---|
| “What meetings do I have tomorrow?” | The assistant resolves tomorrow in your timezone and queries that date. | Matching titles and times. |
| “Add a half-hour planning meeting this Friday at 15:00, with a 10-minute reminder.” | The assistant determines the date and creates a 15:00–15:30 event. | An Outlook event with the requested reminder. |
| “Move the planning meeting to September 30.” | The assistant finds the event and changes its scheduled date. | The same event on the new date, keeping its time and duration. |
| “Every Wednesday at 09:00–09:30, eight times.” | The assistant prepares a weekly rule and a count of eight. | A recurring series in Outlook. |
| “Am I free on September 30 from 14:00 to 17:00?” | The tool subtracts occupied time from that window. | Available intervals, such as 14:00–15:00 and 15:30–17:00. |

You can also search by title, location, notes, category, or creation date; edit event details; delete one occurrence or a whole series; create all-day events; and check the next recurring occurrence.

## Quick start

### 1. Get the project and dependencies

You need Python **3.10+**, an Outlook account, and internet access for sign-in and calendar operations. Conversation-based use also needs an AI agent that can load skills and run local Python commands. Model access is provided by that agent; this repository requires no model download or input dataset.

Clone the repository, or download and extract it, then open a terminal in its root directory:

```bash
git clone https://github.com/Lovely-Qianyun/outlook-calendar-management.git
cd outlook-calendar-management
python -m pip install requests msal tzdata
```

Use `python3` instead of `python` if that is your Python 3.10+ command. Login and calendar commands can also install missing dependencies automatically.

### 2. Connect your calendar

```bash
python scripts/outlook_setup.py
python scripts/outlook_cal.py status --json
```

Follow the device-code sign-in instructions in the terminal. Check that `status` reports `connected: true` and the account you intend to use. The tool requests calendar read/write and mailbox-timezone access. Organization policies may require administrator approval; see [connection setup](references/configuration.md).

### 3. Try a query

Replace the example date and timezone with yours. This command displays seven calendar dates starting on September 28:

```bash
python scripts/outlook_cal.py list --from 2026-09-28 --days 7 --timezone Asia/Shanghai --json
python scripts/outlook_cal.py free 2026-09-30 --from 14:00 --to 17:00 --timezone Asia/Shanghai --json
```

For example, if the only occupied time in that afternoon is 15:00–15:30, the second command returns:

```json
{"2026-09-30": [["14:00", "15:00"], ["15:30", "17:00"]]}
```

### 4. Create an event or use your assistant

The following command **writes a real event** to the connected calendar. Check the date, timezone, and account before running it. Overlap warnings are informational and do not prevent creation.

```bash
python scripts/outlook_cal.py add "Planning" "2026-09-30 15:00" "2026-09-30 15:30" --remind 10 --timezone Asia/Shanghai --json
```

The result contains the created event's `id`, title, times, and reminder fields. Run `read` with that returned ID to inspect it; command details are in the [reference](references/commands.md).

For conversation-based use, place the **complete project folder** in your agent's skill directory and load [SKILL.md](SKILL.md). Then ask, for example, “Check my Outlook calendar for tomorrow.” The assistant translates your request into explicit dates and command parameters.

## Where results go

- **Calendar changes** are stored in the connected account's default Outlook calendar and are visible in Outlook clients signed in to that account.
- **Query results** appear in the terminal, or in the assistant's reply. To save JSON locally, redirect it to a file:

  ```bash
  python scripts/outlook_cal.py list --from 2026-09-28 --days 7 --timezone Asia/Shanghai --json > events.json
  ```

  `events.json` is created in the current directory; the same filename is overwritten on another run. Diagnostics go to stderr separately.
- **Login credentials** are stored at `~/.outlook_cal_token.json` by default. Keep this file private. See [configuration](references/configuration.md) to choose another location or switch accounts.

## More help

| Need | Guide |
|---|---|
| All commands, parameters, and output formats | [Command reference](references/commands.md) |
| Recurring events and one-occurrence/whole-series changes | [Recurring events](references/recurring-events.md) |
| Login, account switching, and custom Azure apps | [Connection setup](references/configuration.md) |
| Installation, authentication, and timezone problems | [Troubleshooting](references/troubleshooting.md) |
| Implementation and offline testing | [Developer guide](DEVELOPMENT.md) |

Licensed under [MIT](LICENSE).
