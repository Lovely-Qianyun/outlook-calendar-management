# 真实日历集成测试

验证 CLI 能否通过 Microsoft Graph 完成一次创建、读取、修改、移动和清理流程。例如，运行脚本会创建一个普通日程和一个重复两次的系列，检查修改结果，再删除本次创建时返回的 ID，最终输出 JSON 报告。

## 准备并运行

需要 Python 3.10+、网络连接和可写入的 Outlook 测试账户。**本流程会改动真实日历**，建议使用专用测试账户；日常开发的离线验证见[开发者指南](../../DEVELOPMENT.zh-CN.md)。

在项目根目录使用 PowerShell，单独保存测试凭据：

```powershell
python -m pip install requests msal tzdata
New-Item -ItemType Directory -Force .local-calendar-test | Out-Null
$env:OCAL_TOKEN_PATH = Join-Path (Get-Location) '.local-calendar-test/outlook-token.json'
python scripts/outlook_setup.py
python scripts/outlook_cal.py status --json
```

登录时选择测试账户。确认 `status` 返回的邮箱后，将下方 `test@example.com` 替换为该邮箱并运行一次：

```powershell
python tests/integration/drill.py --account test@example.com --confirm --lang zh > .local-calendar-test/report.json
```

`--account` 指定预期账户，`--confirm` 允许测试写入及清理；脚本在写入、删除和诊断查询前核对账户，发现不匹配时停止相应操作。测试子进程继承 `OCAL_TOKEN_PATH`。Bash 的凭据设置见[连接配置](../../references/configuration.zh-CN.md)，测试命令相同。

## 结果在哪里

上述命令将 JSON 报告保存到项目根目录下的 `.local-calendar-test/report.json`，再次运行会覆盖同名报告；省略重定向则显示在终端。退出码为 0 且 `ok` 为 `true`，表示检查和清理均成功。

| 报告字段 | 含义 |
|---|---|
| `ok`、`checks`、`errors` | 总体结果、已通过检查及失败信息。 |
| `account`、`subject_prefix`、`test_window` | 目标账户、本次唯一主题前缀、固定查询日期和 UTC 时区。 |
| `remaining_ids` | 本次创建后，尚未确认删除成功的 ID。 |
| `deletion_checks` | 删除回查结果：`absent`、`present` 或 `unverified`；`target_status` 记录原目标 ID 的回读状态，`matching_ids` 记录窗口内仍存在的关联项。 |
| `unknown_create_subjects` | 创建请求未返回可用 ID 的主题，写入结果待核实。 |
| `unknown_create_checks` | 按上述完整主题只读回查的结果：`observed`、`not_found` 或 `unverified`，附匹配 ID 和时间。 |

测试日程在 Outlook 中暂时可见，主题前缀为 `ocal-smoke-...-`，忙碌状态为“空闲”。测试日期从当前 UTC 日期后 30 天开始，固定三天窗口覆盖两个预期出现日期及额外一天。

## 失败后的检查

检查失败后仍会尝试清理，自动删除范围限于本次创建返回的 ID。结果不明的写入会保留在报告中供核实；按主题查到的其他 ID 仅用于诊断。`not_found` 表示固定窗口内未查到。

再次运行前，在报告指定账户与日期窗口中检查 `remaining_ids` 和 `unknown_create_checks`。强制终止进程可能中断清理，可用 `subject_prefix` 定位遗留测试日程。确认遗留项的来源和状态后再处理。

## 覆盖范围

脚本检查本地 `context`、`date` 运算，时段日程的增查改移，`list` 查询，`free` 返回结构，以及每日重复系列的规则和恰好两次出现。清理时核对删除响应的 ID 和系列标记；清理后同时验证固定窗口中没有关联项、原目标 ID（系列使用主事件 ID）返回明确的 `event_not_found` / 404。其他读取错误记为尚未核实。完整参数校验、夏令时、其他重复模式、空闲计算和错误处理由离线测试覆盖。
