---
name: outlook-calendar-management
description: "View, find, add, update, move, and delete Outlook / Microsoft calendar events, including recurring events and free-time queries. Use when the user names Outlook calendar or the conversation already establishes it as the calendar to manage. Does not handle email or other calendar products."
license: "MIT"
metadata:
  version: 3.0.0
---

# Outlook 日历助手

管理已连接账户的默认 Outlook 日历，包括查询、创建、修改、移动、删除、定期日程和空闲查询。结合用户语言与上下文确定目标和参数，再调用项目附带的 Python CLI。

## 请求与结果示例

假设当前是 **2026-09-28，Asia/Shanghai**：

| 用户请求 | 处理方式 | 核实并汇报 |
|---|---|---|
| “明天有哪些安排？” | 查询 `list --from 2026-09-29 --days 1 --json`。 | 当天日程的标题和时间。 |
| “本周五 15:00 加半小时会议，提前十分钟提醒。” | 从本周一加四天得到 10 月 2 日，再创建 15:00–15:30 的日程，传 `--remind 10`。 | 新日程的日期、起止和提醒。 |
| “把昨天加的计划讨论移到今天。” | 用创建日期筛选定位，再执行 `move <ID> --to 2026-09-28 --json`。 | 原发生日期与新日期，保留的时段。 |
| “本周五 14:00–17:00 有空吗？” | 用 `free 2026-10-02 --from 14:00 --to 17:00 --json` 查询。 | 返回的空闲时段。 |

实际日期由当前上下文计算；以上命令还应传入已确定的 `--timezone`。

## 运行入口

相对于本 skill 目录解析路径，使用 Python 3.10+：

```bash
python "<skill目录>/scripts/outlook_cal.py" context --timezone Asia/Shanghai --json --lang zh
```

下文省略解释器与脚本路径。优先使用 `--json`，解析后读取字段；中文对话使用 `--lang zh`，其他语言使用 `--lang en`，回复沿用用户语言。这些选项和 `--timezone` 可放在子命令前或后。

首次连接或切换账户时，按[连接配置](references/configuration.zh-CN.md)运行 `scripts/outlook_setup.py`，用 `status --json` 检查账户。日历命令需要网络和登录；缺失的 requests、msal、tzdata 会自动安装。本地 `context`、`date` 无需登录；地区时区需要系统时区数据或已安装的 tzdata。

## 1. 确定日期、目标和范围

- 相对日期需要当前时间和有效时区。信息不足或已过时时，调用 `context --json`；用户指定时区时加入 `--timezone`。结果含 `now`、`today`、`timezone`、`utc_offset`、`weekday` 和周一日期 `week_start`。
- 用 `date --base YYYY-MM-DD --days N --json` 或 Python 日期运算计算具体日期。例如，本周五为 `week_start` 加四天。后续命令复用同一命名时区。
- CLI 日期格式为补零的 `YYYY-MM-DD`，带时刻为 `YYYY-MM-DD HH:MM` 或 `YYYY-MM-DDTHH:MM`，时区单独传入。时段创建需要开始和结束；全天创建使用 `--all-day`。缺少起止、时长或全天意图时，结合上下文补齐必要信息后再写入。
- ID 来自查询结果的 `id` / `seriesMasterId`。修改或删除前，通过 `read` 或已有的新鲜完整结果确认目标字段；有多个候选时消除歧义，并确定单次或整个系列的范围。用户对已明确操作和范围的授权继续有效。
- 写入前保存已连接账户、目标、操作范围、绝对日期时间、时区和待修改字段，验证和恢复时复用这些值。

## 2. 执行操作

| 任务 | 命令 |
|---|---|
| 按发生日期查询 | `list --from YYYY-MM-DD --days N --json` |
| 筛选上述结果 | 加 `--search "词"`、`--category "类别"` 或 `--reminders` |
| 按创建日期定位 | `list --created-after YYYY-MM-DD --created-before YYYY-MM-DD --json` |
| 详情 / 下次出现 | `read <ID>` / `next <ID>` |
| 创建 / 修改 / 移动 / 删除 | `add` / `update` / `move` / `delete` |
| 空闲时段 | `free YYYY-MM-DD --from HH:MM --to HH:MM --json` |

发生日期查询覆盖 N 个自然日，结束边界为最后一日的次日零点；创建筛选的 `--created-before` 也不含上界。未指定查询范围时，可从 `context.today` 起先查七天，并在汇报中说明。需要标题和时间时使用普通列表；`--summary` 仅返回每日数量。

时段操作使用选定时区，全天写入优先使用邮箱时区，取不到时回退到选定时区。全天结束日期包含当天；时段/全天转换需要同时给新开始和结束。

定期操作先读[定期日程](references/recurring-events.zh-CN.md)。规则用 Graph pattern JSON 文件传入；修改规则操作主事件，保留原截止或次数时需明确传入结束条件。系列规则变更可能重置单独修改或删除过的出现，应在操作前说明这一影响。

`--json` 和适用命令的 `-y` 会跳过终端确认；执行前应已明确用户要求的目标和范围。`--search` 的快捷定位范围为过去七天到未来三十天，其他范围先 `list` 再传 ID。

## 3. 核实并交付结果

创建、修改或移动后回读一次，核对用户要求的字段。删除时，在同一已核实账户下，按保留的目标和范围验证：

- 将删除成功响应中的 `deleted` ID、`series` 标记与预期目标核对：删除某次应对应单次 ID，删除整个系列应对应主事件 ID。不一致时先排查，再进行后续写入。
- 删除普通日程或某次出现后，查询其发生日期窗口，核对目标 ID 已不存在。删除整个系列时，还须用保留的主事件 ID 执行 `read`，取得 `code: event_not_found`、`http_status: 404` 的错误结果。窗口为空本身不足以证明系列已删除；认证、权限或网络错误表示尚未核实。
- 验证失败不构成再次删除的依据。删除结果不明、没有成功响应时，按保留的目标和范围执行同样的只读检查，并仅汇报证据能确认的状态。

写入超时或结果不明时，按保留的 ID 回读；创建未返回 ID 时，在预期日期窗口定位候选并核对请求字段。唯一且能对应本次请求的匹配项满足预期字段时，确认所需结果并停止写入。零匹配、多候选、部分匹配或读取失败时，保留不确定性，停止自动写入并说明已知情况。只有明确证据表明请求未提交或在执行前被拒绝，且原因已排除、已授权目标重新核实后，才复用固定参数重试；助手层面最多重试一次。恢复细节见[故障排查](references/troubleshooting.zh-CN.md#写入结果不明时)。临时读取故障可重试一次；仍失败则说明未能核实的内容。

向用户报告实际结果，修改时给出相关前后值，并说明尚未核实的部分。日历变更保存在 Outlook；查询显示在助手回复中，需要文件时将 JSON 输出保存到用户指定位置。

JSON 操作的 stdout 是一个 JSON 值，诊断在 stderr。检查退出码及错误对象的 `error`、`exit`，有结构化分类时还包含 `code`、`http_status`；`outcome_unknown: true` 表示写入结果不明，缺少该字段不代表可以重试；未连接的 `status` 返回 `connected: false`。空闲 JSON 按日期列出时段，空数组表示该查询窗口没有空闲，完整窗口表示全空闲。

完整参数、输出结构与用例见[命令参考](references/commands.zh-CN.md)。
