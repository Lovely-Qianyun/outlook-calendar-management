🌐 [English](README.md) | 中文

<p align="center">
  <img src="./icon/appIcon.png" alt="Outlook 日历助手图标" width="20%">
</p>

# Outlook 日历助手

通过与 AI 助手对话，或直接在终端运行命令，管理 Outlook 日历。适合查看近期安排、寻找会议空档、调整日程日期，以及维护定期会议和提醒。操作对象是已连接账户的默认日历。

支持个人 Outlook.com 和 Microsoft 365 账户，提供中英文输出。项目包含一份供 AI 助手使用的 skill，以及通过 Microsoft Graph 读写日历的本地 Python 命令行工具。

## 能做什么

| 你提出的需求 | 如何处理 | 得到的结果 |
|---|---|---|
| “明天有哪些会？” | 助手按你的时区确定明天的日期，查询当天日历。 | 匹配的会议标题和时间。 |
| “本周五 15:00 加一个半小时的计划讨论，提前十分钟提醒。” | 助手确定日期，创建 15:00–15:30 的日程。 | Outlook 中带提醒的会议。 |
| “把计划讨论挪到 9 月 30 日。” | 找到目标日程，修改发生日期。 | 同一日程移到新日期，保留原时段和时长。 |
| “每周三 09:00–09:30，共八次。” | 助手整理每周重复规则和次数。 | Outlook 中的定期系列。 |
| “9 月 30 日 14:00 到 17:00 有空吗？” | 从指定窗口中扣除已占用时间。 | 可用时段，例如 14:00–15:00、15:30–17:00。 |

还可以按标题、地点、备注、类别或创建日期查找日程，修改详情，删除单次或整个系列，创建全天日程，以及查询定期日程的下一次出现。

## 快速开始

### 1. 获取项目并安装依赖

需要 **Python 3.10+**、Outlook 账户，以及用于登录和操作日历的网络连接。对话使用还需要能够加载 skill 并运行本地 Python 命令的 AI 助手；模型由该助手提供，本仓库无需下载模型或准备输入数据集。

克隆仓库，或下载并解压项目，然后在项目根目录打开终端：

```bash
git clone https://github.com/Lovely-Qianyun/outlook-calendar-management.git
cd outlook-calendar-management
python -m pip install requests msal tzdata
```

如果你的 Python 3.10+ 命令是 `python3`，将示例中的 `python` 换成 `python3`。登录和日历命令也会自动安装缺失的依赖。

### 2. 连接日历

```bash
python scripts/outlook_setup.py
python scripts/outlook_cal.py status --json
```

按终端提示完成设备码登录。检查 `status` 中的 `connected: true` 和账户信息，确认连接的是要操作的账户。工具申请日历读写和邮箱时区读取权限；组织账户可能需要管理员批准，详见[连接配置](references/configuration.zh-CN.md)。

### 3. 先试一次查询

将示例日期和时区替换为自己的目标值。第一条命令查询从 9 月 28 日开始的七个自然日：

```bash
python scripts/outlook_cal.py list --from 2026-09-28 --days 7 --timezone Asia/Shanghai --json
python scripts/outlook_cal.py free 2026-09-30 --from 14:00 --to 17:00 --timezone Asia/Shanghai --json
```

假设当天下午只有 15:00–15:30 被占用，第二条命令会返回：

```json
{"2026-09-30": [["14:00", "15:00"], ["15:30", "17:00"]]}
```

### 4. 创建日程，或交给助手操作

下面的命令会**向已连接日历写入真实日程**，运行前请核对日期、时区和账户。时间重叠时会显示提醒，但仍会创建日程。

```bash
python scripts/outlook_cal.py add "计划讨论" "2026-09-30 15:00" "2026-09-30 15:30" --remind 10 --timezone Asia/Shanghai --json
```

返回结果包含新日程的 `id`、标题、起止时间和提醒字段。将返回的 ID 传给 `read` 可以查看详情，参数见[命令参考](references/commands.zh-CN.md)。

如需通过对话使用，将**完整项目文件夹**放入助手的 skill 目录，并加载 [SKILL.md](SKILL.md)；中文说明见 [SKILL.zh-CN.md](SKILL.zh-CN.md)。然后可以说：“帮我看看 Outlook 日历明天有什么安排。”助手会把请求整理为具体日期和命令参数。

## 结果在哪里

- **日历变更**保存在已连接账户的默认 Outlook 日历中，可在登录该账户的 Outlook 客户端查看。
- **查询结果**显示在终端或助手回复中。需要保存为本地 JSON 文件时，可以重定向输出：

  ```bash
  python scripts/outlook_cal.py list --from 2026-09-28 --days 7 --timezone Asia/Shanghai --json > events.json
  ```

  `events.json` 位于当前目录，再次使用同名文件会覆盖原内容；诊断信息单独输出到 stderr。
- **登录凭据**默认存放在 `~/.outlook_cal_token.json`，请妥善保管。更换保存位置或切换账户见[连接配置](references/configuration.zh-CN.md)。

## 继续阅读

| 需要了解 | 文档 |
|---|---|
| 完整命令、参数与输出格式 | [命令参考](references/commands.zh-CN.md) |
| 重复规则、单次与整系列操作 | [定期日程](references/recurring-events.zh-CN.md) |
| 登录、切换账户、自有 Azure 应用 | [连接配置](references/configuration.zh-CN.md) |
| 安装、认证与时区问题 | [故障排查](references/troubleshooting.zh-CN.md) |
| 实现原理与离线测试 | [开发者指南](DEVELOPMENT.zh-CN.md) |

使用 [MIT 许可证](LICENSE)。
