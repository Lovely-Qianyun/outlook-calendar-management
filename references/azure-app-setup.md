# Use Your Own Azure Application

Supply your own application client ID when you need to manage the registration and consent. For example, register a public client for a personal Outlook account, sign in, and use the same calendar commands. For a standard connection, use the [built-in application](configuration.md).

## Register and configure

You need an account allowed to register applications in a Microsoft Entra tenant, or an administrator's help. Open **App registrations** in the [Microsoft Entra admin center](https://entra.microsoft.com/), create an application, and record its **Application (client) ID**. Choose account types for the intended users; see Microsoft's [registration guide](https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app).

1. Name the application. Choose personal Microsoft accounts for personal Outlook.com use; organizational users need compatible account support and administrator permission. The current setup script uses the `consumers` / `common` authorities and exposes no tenant-ID argument, so organizational registrations must accommodate those endpoints.
2. Enable **Allow public client flows** in authentication settings and save. This tool uses device-code authentication for public clients; see Microsoft's [public-client guidance](https://learn.microsoft.com/en-us/entra/identity-platform/msal-client-applications).
3. Add Microsoft Graph **delegated permissions** `Calendars.ReadWrite` and `MailboxSettings.Read`. Their purposes are in [connection setup](configuration.md). Complete administrator consent where organization policy requires it.

This sign-in flow uses a client ID and interactive user authorization; it requires no client secret.

## Sign in and check the result

After installing dependencies from the [quick start](../README.md#quick-start), run from the project root, replacing the placeholder with your application's client ID:

```bash
python scripts/outlook_setup.py YOUR_CLIENT_ID
python scripts/outlook_cal.py status --json
```

Follow the terminal's device-code instructions. `status` should report `connected: true` and the expected account. Credentials are saved at `OCAL_TOKEN_PATH`, defaulting to `~/.outlook_cal_token.json`; successful setup replaces any connection stored at that path.

## Connection failures

| Symptom | Check |
|---|---|
| Application not found or account type mismatch | Client ID, supported account types, public-client settings, and organization restrictions. |
| 403 permission error | Delegated permissions and consent; calendar operations need `Calendars.ReadWrite`, mailbox timezone reads need `MailboxSettings.Read`. |
| Expired device code | Run the same setup command again and use the new code. |

For other problems, see [troubleshooting](troubleshooting.md).
