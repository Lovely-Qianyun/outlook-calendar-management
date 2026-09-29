# 命令参考

用命令行查询和修改已连接账户的默认 Outlook 日历。本页按任务列出命令、参数和返回结果；安装与登录见[快速开始](../README.zh-CN.md#快速开始)。

## 示例：查找一个下午的空闲时间

在项目根目录运行，日期和时区替换为实际需求：

```bash
python scripts/outlook_cal.py free 2026-09-30 --from 14:00 --to 17:00 --timezone Asia/Shanghai --json
```

若只有 15:00–15:30 被占用，输出为：

```json
{"2026-09-30": [["14:00", "15:00"], ["15:30", "17:00"]]}
```

结果显示在终端；命令末尾加 `> free.json` 可保存到当前目录，已有同名文件会被覆盖。日历写入保存在 Outlook 中。以下命令均从项目根目录运行；其他目录使用脚本的完整路径。尖括号中的值（如 `<ID>`）需要替换为实际值。

## 共用参数与格式

- `--json`、`--lang zh|en`、`--timezone "Area/City"` 可放在子命令前或后。未给 `--timezone` 时自动探测有效本地时区，包括 `TZ`。显式时区必须是有效 IANA 或现行 Windows 名称；无效名称报错，不静默回退 UTC。IANA 输入保留该地区自身的规则。
- 日期严格为 `YYYY-MM-DD`；带时刻严格为 `YYYY-MM-DD HH:MM` 或 `YYYY-MM-DDTHH:MM`。所有数字字段补零，不接受秒、时区后缀、自然语言或多余空白。时区使用单独参数。
- 模型负责理解自然语言；需要时获取新鲜 `context`，计算日期，写入与重试保留相同的绝对值和时区名称。2026 年 9 月的示例日期均为假设值。
- 日程 ID 使用 JSON 的 `id` 和 `seriesMasterId`。人类输出也提供 🆔 和 🆕 锚点；stderr 中的冲突提示不是操作结果 ID。
- `update`、`move`、`delete` 接受日程 ID 或 `--search "词"`。搜索范围为过去 7 天至未来 30 天；唯一匹配继续执行，无匹配或多匹配时报错并提示。需要其他范围或已经明确目标时，先用 `list` 查询，再传入返回的 ID。
- `-y` 和 `--json` 跳过 CLI 确认；模型复用用户已对具体操作与范围给出的授权。

## 本地工具

### context — 当前时钟与时区

```bash
python scripts/outlook_cal.py context --timezone Asia/Shanghai --json
```

返回对象含 `now`（带偏移的时间）、`today`（日期）、`timezone`（有效时区名称）、`utc_offset`、`weekday`（英文小写星期）、`week_start`（本周一日期）。不读取日历，不进行账户认证。相关步骤可以复用新鲜结果；时间流逝或时区改变影响相对日期含义时再刷新。

### date — 确定的自然日运算

```bash
python scripts/outlook_cal.py date --base 2026-09-07 --days 4 --json
```

返回 `{"base":"2026-09-07","days":4,"date":"2026-09-11"}`。`--base` 和有符号整数 `--days` 必填，允许零和负值。不读取时钟，不访问日历；非法日期或计算越界时报错。

明天用 `context.today` 加 1 天，本周五用 `context.week_start` 加 4 天，下周一加 7 天。复杂月/年运算可用 Python `datetime`/`calendar`，同样传入明确基准日期。

## 读取命令

### status

`status` 报告连接状态与账户信息。与 `context` 不同，它会检查账户配置。

### list

选择一种查询依据：

- `list --from YYYY-MM-DD [--days N]`：覆盖 N 个自然日，默认 7 天，N 必须为正数。从有效时区当日零点到最后一天的次日零点，不含结束边界。跨夏令时边界时分别计算两端偏移。
- `list --created-after YYYY-MM-DD [--created-before YYYY-MM-DD]`：按创建时间筛选，大于等于前一个日期的本地零点，并可选地小于后一个日期的零点。上界日期必须更晚。筛选的是创建时间，不是发生时间。`--created-before` 必须配合 `--created-after`，创建筛选不能与 `--from` 合用。

`--search "词"` 筛选标题/地点/备注，`--category "类别"` 筛选类别，`--reminders` 只看开启提醒的日程。`--summary` 按返回日程的开始日期计数，跨多天的日程只计一次；需要标题和时间时不加该选项。JSON 模式返回日期到数量的对象，如 `{"2026-09-11":2}`，无匹配时为 `{}`。创建日期筛选结果还包含 `createdDateTime`。

```bash
python scripts/outlook_cal.py list --from 2026-09-09 --days 7 --timezone Asia/Shanghai --json
python scripts/outlook_cal.py list --from 2026-09-07 --days 7 --search "会议" --timezone Asia/Shanghai --json
python scripts/outlook_cal.py list --created-after 2026-09-08 --created-before 2026-09-09 --timezone Asia/Shanghai --json
```

### read 与 next

`read <ID>` 返回完整详情，包括创建时间、组织者、提醒、重复规则和适用时的系列主 ID。`next <ID>` 查找未来 365 天内定期日程的下次出现；系列已结束和非定期日程有各自的结果。

### free

`free YYYY-MM-DD [--from HH:MM] [--to HH:MM] [--days N]` 必须给出日期。时段默认 09:00–18:00，N 默认 1；模型应明确传入用户要求的起止时刻。N 为正数，每日结束晚于开始，`HH:MM` 必须补零。标记为空闲或已取消的日程不占用时间，忙碌的全天日程占满当天。若每日窗口端点不存在/有歧义，或窗口内 UTC 偏移发生变化，则拒绝查询。先明确实际 UTC 起止，再用 `--timezone UTC` 查询；纯 `HH:MM` 输出无法区分重复出现的本地时刻。

```bash
python scripts/outlook_cal.py free 2026-09-11 --from 14:00 --to 17:00 --timezone Asia/Shanghai --json
```

## add — 创建日程

时段日程：`add <标题> "YYYY-MM-DD HH:MM" "YYYY-MM-DD HH:MM"`。开始和结束都必填，结束必须晚于开始。只给日期却不加 `--all-day` 会报错。

全天日程：`add <标题> YYYY-MM-DD [YYYY-MM-DD] --all-day`。可选结束日期为包含当天的上界，省略时创建单天日程。后端转换为 Graph 不包含的次日零点。全天写入使用邮箱时区，不可用时使用有效时区。

| 参数 | 含义 |
|---|---|
| `-l` / `--location`、`-b` / `--body` | 地点、备注 |
| `--category "工作,重要"` | 逗号分隔的类别 |
| `--remind N` | 非负数；时段日程提前 N 分钟，全天日程提前 N 天，全天上限 1826 天 |
| `--repeat-file <路径>` 或 `--repeat '<JSON>'` | 经校验的 Graph recurrence pattern，二选一 |
| `--repeat-until YYYY-MM-DD` 或 `--repeat-times N` | 结束条件，二选一，需同时给出规则 |
| `--importance low\|normal\|high`、`--private` | 重要性、隐私 |
| `--busy free\|tentative\|busy\|oof\|workingElsewhere` | 空闲/忙碌状态 |
| `--force` | 跳过冲突检查 |

重叠会警告，不阻断创建。非法、不存在或因夏令时而有歧义的墙钟时间会被拒绝。遇到重复的本地时刻，先确定实际时刻，再使用明确的 UTC 起止值及 `--timezone UTC`。

```bash
python scripts/outlook_cal.py add "计划讨论" "2026-09-11 15:00" "2026-09-11 15:30" --remind 10 --timezone Asia/Shanghai --json
python scripts/outlook_cal.py add "旅行" 2026-09-11 2026-09-13 --all-day --timezone Asia/Shanghai --json
```

## update — 修改指定字段

`update <ID> [参数]` 保留未指定字段。可修改：`--subject`、`--start`、`--end`、`-l`/`--location`、`-b`/`--body`、`--category`、`--importance`、`--private`/`--no-private`、`--busy`、`--remind`/`--no-remind`，以及 `add` 的重复规则选项。

- 空字符串可清空标题、地点、备注、类别，`--no-remind` 关闭提醒。
- 日程类型不变时，可只修改开始或结束，最终时间范围仍须有效。
- 使用 `--all-day`/`--no-all-day` 在全天与时段之间转换时，必须明确给出新类型格式的 **`--start` 和 `--end`**。全天结束日期仍包含当天。
- 只有显式 `--repeat ''` 才移除重复规则；空规则文件或只有空白的文件会报错。设置规则传 pattern 对象或文件。单次/系列范围及结束条件见 [recurring-events.zh-CN.md](recurring-events.zh-CN.md)。
- 没有修改字段时返回错误，不发送 PATCH。

```bash
python scripts/outlook_cal.py update <ID> --no-all-day --start "2026-09-11 09:00" --end "2026-09-11 10:00" --timezone Asia/Shanghai --json
```

定期规则的创建与修改示例见[定期日程](recurring-events.zh-CN.md)。

## move 与 delete

`move <ID> --to YYYY-MM-DD` 或 `move <ID> --days N` 必须二选一。有符号的 `--days` 平移发生日期，`--to` 指定实际目的日期。两者保留原时段与时长，包括全天跨度。目的日期指日程实际发生的日期。

`delete <ID> [-y] [--series]` 删除目标日程。目标为单次出现时，`-y`/`--json` 默认只删除该次，`--series` 删除整个系列；交互模式可选择删除范围。从对话确认实际目标与范围。

## JSON 契约

`--json` 操作模式下 stdout 严格为一个 JSON 值，人类诊断信息走 stderr；`--help` 仍为文本。JSON 使用 ASCII 转义保护 Windows 窄编码管道中的 Unicode，先解析再读取字段。

| 命令 | 结果 |
|---|---|
| `context` | 上述时钟/时区对象 |
| `date` | `{base, days, date}` |
| `status` | 连接状态、账户、有效期和当前日期 |
| `next` | 包含下次出现的一项数组；查询窗口内未找到时为 `{"ended": true}` |
| `list` | 日程数组，`--summary` 时为每日数量 |
| `add`、`read`、`update`、`move` | 日程对象 |
| `delete` | 包含 `deleted`、`subject`、`series` 的对象 |
| `free` | `{日期: [[开始, 结束], ...]}`；空数组表示窗口内没有空闲 |
| 操作/参数错误 | `{"error": ..., "exit": 1}`，非零退出 |
| 未连接的 `status` | 含 `connected: false` 的连接状态对象 |

JSON 错误保留 `error` 和 `exit`，Graph/网络错误还可包含以下字段：

| 字段 | 用途 |
|---|---|
| `code` | 与语言无关的分类：`event_not_found`、`authentication_required`、`permission_denied`、`network_error`、`graph_error`、`occurrence_boundary` 或 `invalid_response`。 |
| `http_status` | 已取得的 HTTP 状态码；网络故障可能没有响应。 |
| `outcome_unknown` | 为 `true` 时表示写入可能已执行，例如超时、服务端错误或成功响应无法解析。缺少该字段不构成安全重试的依据。 |

核实日程不存在时，使用 `read` 返回的 `code: event_not_found` 和 `http_status: 404`，并核对账户与 ID。恢复步骤见[故障排查](troubleshooting.zh-CN.md#写入结果不明时)。
