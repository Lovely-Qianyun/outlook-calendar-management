# Outlook Calendar Assistant

A toolkit that lets an AI assistant (agent) manage your Outlook calendar (Microsoft account / outlook.com) through conversation. Just express a need (e.g. "what times are free on Friday afternoon?" or "move the weekly sync to Wednesday") and the AI handles the rest: view, add, modify, move, and delete events, including recurring events (e.g. a meeting that repeats every Monday) and free-time lookup. No need to open the Outlook app - your calendar stays in sync across phone, computer, and web.

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

## Project Structure

```
outlook-calendar-management/
├── SKILL.md            # Agent operation manual, Chinese (when to trigger + how to use)
├── SKILL_EN.md         # Same, English
├── DEVELOPMENT.md      # Developer docs: output protocol, design decisions, testing approach
├── scripts/            # All implementation (pure Python, no framework)
├── tests/              # Unit tests + trigger evaluation set + optional live dry-runs
└── references/         # User docs: command reference, recurring events, configuration, troubleshooting
```

## Testing

- **300 offline unit tests** (pytest): cover the functional modules; all network calls are mocked (no network, no real account needed), runnable anytime; GitHub Actions runs them on Linux/Windows/macOS × Python 3.10/3.13
- **Trigger evaluation set** (`tests/trigger-eval.md`): a complete set of examples of what should trigger this skill and what shouldn't. When you change the trigger description in SKILL.md, check against it to prevent missed and false triggers
- **Output-protocol evaluation set** (`tests/protocol-eval.md` + `tests/test_protocol.py`): the regexes agents use to extract 🆔 / free slots / errors are pinned one by one, so output-format changes can't silently break downstream parsing
- **Optional live dry-runs**: 106 checks against a real Outlook account to verify compatibility with the real service (requires a dedicated test account; see `tests/integration/`)

## Development

To contribute, start with `DEVELOPMENT.md` - it covers the full output protocol, key design decisions, i18n (internationalization) conventions, and official Graph API documentation links.

Core principles:

- **Never break the output protocol**: the output format is a contract that users and scripts depend on; change it with extreme care
- **Keep zh output word-for-word stable**: the copy is pinned by tests verbatim; changes require syncing the test assertions and bumping the version number - do not change it casually
- **Run regression before changing behavior**: whenever behavior changes, run the full test suite first to make sure nothing is broken
