🌐 English | [中文](README.zh-CN.md)

# Outlook Calendar Assistant

*Chat-driven Outlook calendar management for AI agents: events, recurring series, free-time lookup — local, official Graph API, no MCP server.*

Let your AI assistant run your Microsoft Outlook calendar just by chatting. View, add, edit, move and delete events, manage recurring series, and find free time slots — all through natural language. A pure-local Python tool built on the official Microsoft Graph API (personal outlook.com / Microsoft 365 accounts), with one-time device-code login that renews automatically. No external MCP server, no background service. Timezone-aware, understands relative times like "next Tuesday 3pm", and answers in English or Chinese.

## Features

- Full calendar operations: view, search by title / location / category, add, modify, move, delete
- Recurring events: create, edit a single occurrence, edit the series rule, delete the whole series, query the next occurrence
- Free-time lookup: ask "what time is free on Friday afternoon" and get the answer directly
- Bilingual output, auto-selected by system language; override with `--lang zh|en` or the `OCAL_LANG` environment variable
- Auto-installs dependencies on first run (including the `tzdata` timezone database, so times resolve correctly on Windows); no manual install
- Relative times accepted directly: `today`/`tomorrow`/`this Friday`/`2 pm today` are resolved against the system clock at run time
- Machine-readable: append `--json` to any command for clean JSON output, ready for other programs to consume
- Reliably parseable output: event IDs are always marked with 🆔 (see "How It Works"), so agents and scripts can always find the events

## Quick Start

Put the whole project directory into your agent's skills directory (e.g. Hermes, Claude Code), and the agent can manage your calendar for you. You can also run the commands manually in a terminal:

```bash
# First use: sign in. The terminal shows a code;
# open microsoft.com/link in your browser and enter it
python scripts/outlook_setup.py

# See the next 7 days
python scripts/outlook_cal.py list --days 7

# Add an event: title, start time, end time, optional reminder (minutes before)
python scripts/outlook_cal.py add "Weekly meeting" "2026-08-10 09:00" "2026-08-10 10:00" --remind 10
```

Dependencies - `requests`, `msal`, `tzdata` - are auto-installed on first run; no manual install needed. After authenticating once, the login renews automatically; credentials are stored at `~/.outlook_cal_token.json` in your home directory.

## Usage Examples

```
$ python scripts/outlook_cal.py list --days 3
📅 Mon, Aug 10
    🕐 08/10 09:00 - 08/10 10:00  Weekly meeting 🔁Weekly on Monday [Work]
    🆔 AAMkAD...

$ python scripts/outlook_cal.py free "2026-08-14" --from 09:00 --to 18:00
📅 Fri, Aug 14: free 09:00-10:00, 14:00-18:00

$ python scripts/outlook_cal.py delete <ID> -y
🗑️ Removed this occurrence "Weekly Meeting" (other occurrences kept)
```

The 🆔 line in the output is that event's ID; every modify, delete, and move operation takes it from there.

## How It Works

The overall design idea is simple: **output is always predictable and verifiable** - machines never misread it, and humans never get confused. Three pillars support this goal:

- **Official Microsoft API - equivalent to doing it by hand**: the program calls Microsoft Graph API, Microsoft's official interface for the Outlook calendar. The effect is identical to operating Outlook yourself, and changes sync in real time to phone, computer, and web. Sign-in uses the device-code flow: the first run shows you a code, open microsoft.com/link in your browser and enter it; afterwards the login renews automatically via Microsoft's auth library (`msal`). **No local service runs in the background**
- **Timezones handled automatically, following your computer**: all times are parsed, displayed, and converted in the computer's local timezone (official Windows timezone names and IANA names are fully mapped); no manual timezone conversion is needed. Set the `TZ` environment variable to override when detection fails
- **All-day events are written in the mailbox's preferred timezone**: they never span two days in Outlook even when the computer's timezone differs from the account's (after upgrading, re-run `python outlook_setup.py` once to grant the new permission)
- **Output follows a fixed "protocol" - machines never misread it**: the output format is fixed - every event's ID always appears on the line starting with 🆔 (e.g. `AAMkAD...` in the examples), and times, locations, categories, etc. have fixed formats and markers. These markers (emoji anchors) are language-independent - Chinese and English output share the same set - so agents and scripts parse reliably in any language. For programmatic use (e.g. your own scripts), append `--json` for clean JSON output with no human-oriented text mixed in

## Development

For development, start with [DEVELOPMENT_EN.md](DEVELOPMENT_EN.md) — it covers the full output protocol, key design decisions, i18n conventions, and testing.
