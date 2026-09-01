# 命令参考

本文档是 Outlook 日历助手（通过命令行管理 Outlook 日历的工具集）的完整命令参考。
前置条件：已完成连接认证（见 `configuration.zh-CN.md`）；所有命令形如 `python outlook_cal.py <命令> [参数]`，在项目 `scripts/` 目录下运行。

## 目录

- [通用约定](#通用约定)
- [1. 查看安排](#1-查看安排)（status / list / today / tomorrow / week / read / free / next）
- [2. 添加日程：add](#2-添加日程add)
- [3. 修改日程：update](#3-修改日程update)
- [4. 移动日程：move](#4-移动日程move)
- [5. 删除日程：delete](#5-删除日程delete)
- [6. 机器可读输出：--json](#6-机器可读输出json)

## 通用约定

- **时间格式**：时段用 `YYYY-MM-DD HH:MM`，如 `2026-08-10 09:00`；全天只用 `YYYY-MM-DD`。**也支持相对时间**：`今天`/`明天`/`后天`/`本周X`/`下周X`（可带时刻：`今天 14:00`、`今天下午2点`、`明天上午9点半`），按命令运行时的系统当前日期换算
- **事件 ID**：须从命令输出的 🆔 行获取，不能凭空构造；`list` / `add` / `read` 均可获得
- **--search 定位**：`update` / `delete` / `move` 不传事件 ID 时可用 `--search "词"` 按标题/地点/备注定位（唯一匹配直接操作；多匹配报错并列出候选 🆔；搜索窗口为过去 7 天 ~ 未来 30 天）
- **确认**：`update` / `delete` / `move` 默认会询问一次确认，`-y` 可跳过；`--json` 时自动跳过
- **语言**：默认按系统语言自动选择（中文系统 → 中文，其他 → 英文）；`--lang zh|en`（命令前后均可）或环境变量 `OCAL_LANG` 覆盖。`--json` 输出与 emoji 锚点语言无关
- **首次运行**：自动安装缺失依赖（requests/msal/tzdata）；安装失败时会提示手动安装命令。`tzdata` 是 Windows 时区解析正确的关键，缺失可能导致时间偏移
- **机器可读**：任意命令加 `--json` → stdout 只输出 JSON（用法见最后一节）

---

## 1. 查看安排

### status — 连接状态
`status`：显示当前账户、登录有效期。

### list — 查看一段时间的日程
默认未来 7 天，按天分组显示（时间、标题、定期标记、类别、🆔）。

| 参数 | 作用 |
|------|------|
| `--days N` | 查看未来 N 天（默认 7） |
| `--past N` | 同时查看过去 N 天 |
| `--from YYYY-MM-DD` | 从指定日期开始查看（此时忽略 `--past`） |
| `--search "词"` | 按标题/地点/备注筛选 |
| `--category "类别"` | 按类别筛选 |
| `--created-after 日期` | 仅查看此后**添加**的日程（"我昨天加的"） |
| `--reminders` | 仅查看设置了提醒的日程 |
| `--summary` | 仅显示每天日程数量，不列出明细 |

```bash
python outlook_cal.py list --days 30 --past 7 --category "工作"
python outlook_cal.py list --from "2026-08-20" --days 5 --summary
python outlook_cal.py list --created-after "2026-08-06" --search "会议"
```

### today / tomorrow / week — 快捷查看
今天 / 明天 / 未来 7 天。均支持 `--search` / `--category` / `--summary`。

### read — 日程详情
`read <ID>`：完整信息（时间、地点、类别、重复规则、重要度、私密、备注、链接、添加时间、组织者）。若是定期日程的某一次，还会显示所属系列、第 N 次、系列主事件 ID。

### free — 空闲时段
`free [日期] [--from HH:MM] [--to HH:MM] [--days N]`（默认今天 09:00-18:00，1 天）。
按"忙碌/空闲"状态判断：标记为"空闲"的日程不视为占用；全天日程占用整天。

### next — 定期日程的下次出现
`next <ID>`：返回未来 365 天内的下一次出现；系列已结束时会有明确提示；非定期日程会报错。

---

## 2. 添加日程：add

`add <标题> <开始> [结束]` —— 省略结束时间时，默认开始后 1 小时。

| 参数 | 作用 |
|------|------|
| `--all-day` | 全天（开始只给日期） |
| `-l "地点"` | 地点 |
| `-b "备注"` | 备注 |
| `--category "工作,重要"` | 类别（逗号分隔多个） |
| `--remind N` | 提醒：全天 = 提前 N **天**；时段 = 提前 N **分钟** |
| `--repeat "规则"` | 定期（语法见 recurring-events.zh-CN.md） |
| `--repeat-until 日期` / `--repeat-times N` | 定期结束条件（需配合 `--repeat`） |
| `--importance 低/普通/高` | 重要度 |
| `--private` | 私密 |
| `--busy busy/free/tentative/oof/workingElsewhere` | 忙闲显示 |
| `--force` | 跳过冲突检查 |

注意：
- 仅给出日期而未给时间时，自动按全天处理（会提示）
- 全天日程可给定第二个日期参数表示多天（`add "旅行" "2026-08-10" "2026-08-12" --all-day`）
- 默认检查与现有日程的重叠情况，仅警告不阻断；`--force` 可跳过

```bash
python outlook_cal.py add "周会" "2026-08-10 09:00" "2026-08-10 10:00" -l "3号会议室" -b "讨论Q3" --category "工作" --remind 10
python outlook_cal.py add "生日" "2026-08-15" --all-day
python outlook_cal.py add "旅行" "2026-08-10" "2026-08-12" --all-day
python outlook_cal.py add "站会" "2026-08-14 10:00" "2026-08-14 10:30" --repeat "每周五" --repeat-times 5
```

---

## 3. 修改日程：update

`update [<ID>] [参数]` —— 仅修改给定的字段，其余不变；不传 ID 时可用 `--search` 定位目标。

| 参数 | 作用 |
|------|------|
| `--search "词"` | 不传事件 ID 时按关键词定位（唯一匹配直接操作；多匹配报错列出候选） |
| `--subject "新标题"` | 修改标题（`""` 表示清空） |
| `--start` / `--end` | 修改时间（全天给日期，时段给 `日期 时间`） |
| `--all-day` / `--no-all-day` | 全天 ↔ 时段互转 |
| `-l` / `-b` | 地点 / 备注（`""` 表示清空） |
| `--category` | 类别（`""` 表示清空） |
| `--importance` / `--private`/`--no-private` / `--busy` | 重要度 / 私密 / 忙闲 |
| `--remind N` / `--no-remind` | 设置提醒 / 关闭提醒 |
| `--repeat "规则"` / `--repeat ""` | 设置定期 / 解除定期（转为单次） |
| `--repeat-until` / `--repeat-times` | 定期结束条件（需配合 `--repeat`） |
| `-y` | 跳过确认 |

注意：
- 转为时段未给 `--end` 时，默认开始后 1 小时
- 全天日程同时给定 `--start` 与 `--end` 两个日期，可改为多天区间
- 对定期日程"某一次"的修改仅影响该次；修改整个系列的规则须操作主事件（见 recurring-events.zh-CN.md）

---

## 4. 移动日程：move

`move [<ID>] --days N` 或 `move [<ID>] --to YYYY-MM-DD`（二选一）；不传 ID 时可用 `--search` 定位目标。

- **保留原来的时间段和时长**，只改日期（全天日程同理）
- `--days` 可为负数（向前移动）

```bash
python outlook_cal.py move <ID> --days 3          # 整体往后 3 天
python outlook_cal.py move <ID> --to "2026-08-20" # 挪到 8 月 20 日
python outlook_cal.py move --search "站会" --to "2026-08-20"  # 按标题定位后移动
```

---

## 5. 删除日程：delete

`delete [<ID>] [-y] [--series]`；不传 ID 时可用 `--search` 定位目标。

| 参数 | 作用 |
|------|------|
| （无） | 默认先确认；若目标为定期日程的某一次，会询问"仅删本次 [1] / 删整个系列 [2]" |
| `--search "词"` | 不传事件 ID 时按关键词定位（唯一匹配直接操作；多匹配报错列出候选） |
| `-y` | 跳过确认；定期日程默认**只删本次** |
| `--series` | 删除整个定期系列 |

---

## 6. 机器可读输出：--json

任意命令前或后加 `--json`：
- stdout 只有 JSON，人类提示走 stderr
- list → 日程数组；add/read/update → 日程对象；delete → `{"deleted", "subject", "series"}`；free → 按天结构；出错 → `{"error", "exit": 1}`
- update/delete/move 的确认流程自动跳过
