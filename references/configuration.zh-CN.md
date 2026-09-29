# 连接 Outlook 日历

连接个人 Outlook.com 或 Microsoft 365 账户后，即可查询和修改其默认日历。例如，登录后用 `status --json` 确认当前账户，再用 `list` 获取该账户的日程。

## 登录并检查连接

需要 Python 3.10+ 和网络连接。在项目根目录运行：

```bash
python -m pip install requests msal tzdata
python scripts/outlook_setup.py
```

登录命令使用内置应用，终端会显示设备码操作说明。打开提示中的验证网址，输入验证码，使用要操作的账户登录。登录和日历命令也会自动安装缺失的依赖。

日历授权申请以下权限：

| 权限 | 用途 |
|---|---|
| `Calendars.ReadWrite` | 查询、创建、修改、移动和删除日程。 |
| `MailboxSettings.Read` | 读取邮箱时区，用于处理全天日期。 |

组织可能限制应用授权或设备码登录。遇到限制时，请联系管理员确认应用及所需权限；需要使用获准的自有应用时，参见 [Azure 应用配置](azure-app-setup.zh-CN.md)。

登录完成后运行：

```bash
python scripts/outlook_cal.py status --json
python scripts/outlook_cal.py list --from 2026-09-28 --days 7 --timezone Asia/Shanghai --json
```

写入日历前核对 `connected: true` 和 `account`。查询日期及时区按实际需求替换。查询结果显示在终端，日历变更保存在已连接的 Outlook 账户中。

## 凭据与重新连接

凭据默认保存在 `~/.outlook_cal_token.json`，其中 `~` 代表当前用户的主目录。请妥善保管此文件，避免提交到版本库。已有授权仍有效时，工具会自动续期。

切换账户，或授权过期、被撤销时，重新运行 `python scripts/outlook_setup.py`，再通过 `status --json` 核对。成功登录会替换当前凭据路径中保存的连接。

使用自有 Azure 应用时，按 [Azure 应用配置](azure-app-setup.zh-CN.md)传入其客户端 ID。

## 单独保存测试凭据

例如，可以保留常用账户的登录，把测试账户凭据放到 `.local-calendar-test/outlook-token.json`。在**登录和运行日历命令之前**设置 `OCAL_TOKEN_PATH`，并在测试所用终端中持续保留该设置。父目录需要存在。

在项目根目录使用 PowerShell：

```powershell
New-Item -ItemType Directory -Force .local-calendar-test | Out-Null
$env:OCAL_TOKEN_PATH = Join-Path (Get-Location) '.local-calendar-test/outlook-token.json'
python scripts/outlook_setup.py
python scripts/outlook_cal.py status --json
```

Bash 对应写法：

```bash
mkdir -p .local-calendar-test
export OCAL_TOKEN_PATH="$PWD/.local-calendar-test/outlook-token.json"
python scripts/outlook_setup.py
python scripts/outlook_cal.py status --json
```

该目录已被 Git 忽略。路径决定凭据保存位置，登录时选择的账户决定实际访问哪个日历。运行[实机集成测试](../tests/integration/README.zh-CN.md)前，请核对账户邮箱。

恢复默认凭据路径时，可打开未设置该变量的终端，或在 PowerShell 中运行 `Remove-Item Env:OCAL_TOKEN_PATH`，在 Bash 中运行 `unset OCAL_TOKEN_PATH`。

## 时区与语言

用 `--timezone Asia/Shanghai` 或其他 IANA/Windows 时区名称，指定时段日程和查询窗口的时区。全天写入优先使用邮箱时区，不可用时回退到选定时区。若邮箱时区读取失败，且邮箱与本机时区不同，请先重新授权相应权限，再进行依赖全天日期的操作。

终端文案用 `--lang zh` 或 `--lang en` 选择，也可以在当前会话设置 `OCAL_LANG`。JSON 字段名保持一致。完整格式见[命令参考](commands.zh-CN.md)，连接问题见[故障排查](troubleshooting.zh-CN.md)。
