# Connect an Outlook Calendar

Connect a personal Outlook.com or Microsoft 365 account so the tool can query and change its default calendar. For example, after sign-in, `status --json` identifies the connected account and `list` returns its events.

## Sign in and check the connection

Use Python 3.10+ with network access. Run from the project root:

```bash
python -m pip install requests msal tzdata
python scripts/outlook_setup.py
```

The setup command uses the built-in application and prints device-code instructions. Open the displayed verification URL, enter the code, and sign in with the intended account. Login and calendar commands also install missing dependencies automatically.

The calendar authorization requests are:

| Permission | Purpose |
|---|---|
| `Calendars.ReadWrite` | Query, create, edit, move, and delete calendar events. |
| `MailboxSettings.Read` | Read the mailbox timezone used for all-day dates. |

An organization may restrict application consent or device-code sign-in. If access is blocked, ask its administrator about the application and requested permissions, or follow the [custom app guide](azure-app-setup.md) for an approved registration.

After sign-in:

```bash
python scripts/outlook_cal.py status --json
python scripts/outlook_cal.py list --from 2026-09-28 --days 7 --timezone Asia/Shanghai --json
```

Check `connected: true` and `account` before calendar writes. Replace the query date and timezone with your intended values. Results appear in the terminal; calendar changes appear in the connected Outlook account.

## Credentials and reconnection

Credentials are saved in `~/.outlook_cal_token.json` by default, where `~` is your user home directory. Keep this file private and out of version control. The tool refreshes the login while the stored authorization remains valid.

To switch accounts or recover from expired/revoked authorization, rerun `python scripts/outlook_setup.py` and check `status --json`. Successful setup replaces the connection saved at the current token path.

For a custom Azure application, pass its client ID as described in [Azure app setup](azure-app-setup.md).

## Separate test credentials

For example, you can keep your usual login and save a test account's credentials in `.local-calendar-test/outlook-token.json`. Set `OCAL_TOKEN_PATH` **before both setup and calendar commands**, and keep it set in the terminal used for testing. The parent directory must exist.

PowerShell, from the project root:

```powershell
New-Item -ItemType Directory -Force .local-calendar-test | Out-Null
$env:OCAL_TOKEN_PATH = Join-Path (Get-Location) '.local-calendar-test/outlook-token.json'
python scripts/outlook_setup.py
python scripts/outlook_cal.py status --json
```

Bash equivalent:

```bash
mkdir -p .local-calendar-test
export OCAL_TOKEN_PATH="$PWD/.local-calendar-test/outlook-token.json"
python scripts/outlook_setup.py
python scripts/outlook_cal.py status --json
```

The directory is ignored by Git. The path selects a credential file; the account chosen during sign-in determines which calendar is accessed. Verify its email before running the [live integration test](../tests/integration/README.md).

To return to the default credential file, start a terminal without this setting, or clear it with `Remove-Item Env:OCAL_TOKEN_PATH` in PowerShell / `unset OCAL_TOKEN_PATH` in Bash.

## Timezone and language

Use `--timezone Asia/Shanghai` (or another IANA/Windows timezone name) to select the timezone for timed events and query windows. All-day writes use the mailbox timezone when available, falling back to the selected timezone. If mailbox-timezone access fails, reconnect with the required permission before relying on all-day dates across different timezones.

Use `--lang zh` or `--lang en` for terminal messages, or set `OCAL_LANG` for the session. JSON keys stay the same. Full formats are in the [command reference](commands.md); connection errors are covered in [troubleshooting](troubleshooting.md).
