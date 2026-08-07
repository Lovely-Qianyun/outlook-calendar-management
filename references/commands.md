# 命令参考

所有命令形如：`python outlook_cal.py <命令> [参数]`。

## 通用约定

- **时间格式**：时段用 `YYYY-MM-DD HH:MM`，如 `2026-08-10 09:00`；全天只用 `YYYY-MM-DD`
- **事件 ID**：从命令输出的 🆔 行拿，不能凭空构造；`list` / `add` / `read` 都能拿到
- **确认**：`update` / `delete` / `move` 默认会问一次确认，`-y` 跳过；`--json` 时自动跳过
- **语言**：默认按系统语言自动选择（中文系统 → 中文，其他 → 英文）；`--lang zh|en`（命令前后均可）或环境变量 `OCAL_LANG` 覆盖。`--json` 输出与 emoji 锚点语言无关
- **首次运行**：自动安装缺失依赖（requests/msal/tzdata）；失败会提示手动安装命令。`tzdata` 保证 Windows 时区解析正确，缺了时间可能偏移
- **机器可读**：任意命令加 `--json` → stdout 只输出 JSON（用法见最后一节）

---

## 1. 查看安排

### status — 连接状态
`status`：显示当前账户、登录有效期。

### list — 查看一段时间的日程
默认未来 7 天，按天分组显示（时间、标题、定期标记、类别、🆔）。

| 参数 | 作用 |
|------|------|
| `--days N` | 看未来 N 天（默认 7） |
| `--past N` | 同时看过去 N 天 |
| `--from YYYY-MM-DD` | 从指定日期开始看（此时忽略 `--past`） |
| `--search "词"` | 按标题/地点/备注筛选 |
| `--category "类别"` | 按类别筛选 |
| `--created-after 日期` | 只看这之后**添加**的日程（"我昨天加的"） |
| `--reminders` | 只看设置了提醒的日程 |
| `--summary` | 只显示每天几条，不列明细 |

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
按"忙碌/空闲"判断：标记为"空闲"的日程不算占用；全天日程占整天。

### next — 定期日程的下次出现
`next <ID>`：返回未来 365 天内的下一次；系列已结束会明确提示；非定期日程会报错。

---

## 2. 添加日程：add

`add <标题> <开始> [结束]` —— 不写结束时间 = 开始后 1 小时。

| 参数 | 作用 |
|------|------|
| `--all-day` | 全天（开始只给日期） |
| `-l "地点"` | 地点 |
| `-b "备注"` | 备注 |
| `--category "工作,重要"` | 类别（逗号分隔多个） |
| `--remind N` | 提醒：全天 = 提前 N **天**；时段 = 提前 N **分钟** |
| `--repeat "规则"` | 定期（语法见 recurring-events.md） |
| `--repeat-until 日期` / `--repeat-times N` | 定期结束条件（需配合 `--repeat`） |
| `--importance 低/普通/高` | 重要度 |
| `--private` | 私密 |
| `--busy busy/free/tentative/oof/workingElsewhere` | 忙闲显示 |
| `--force` | 跳过冲突检查 |

注意：
- 只给日期没给时间 → 自动按全天处理（会提示）
- 默认检查与现有日程重叠，只警告不阻断；`--force` 跳过

```bash
python outlook_cal.py add "周会" "2026-08-10 09:00" "2026-08-10 10:00" -l "3号会议室" -b "讨论Q3" --category "工作" --remind 10
python outlook_cal.py add "生日" "2026-08-15" --all-day
python outlook_cal.py add "站会" "2026-08-14 10:00" "2026-08-14 10:30" --repeat "每周五" --repeat-times 5
```

---

## 3. 修改日程：update

`update <ID> [参数]` —— 只改给的字段，其余不变。

| 参数 | 作用 |
|------|------|
| `--subject "新标题"` | 改标题（`""` 清空） |
| `--start` / `--end` | 改时间（全天给日期，时段给 `日期 时间`） |
| `--all-day` / `--no-all-day` | 全天 ↔ 时段互转 |
| `-l` / `-b` | 地点 / 备注（`""` 清空） |
| `--category` | 类别（`""` 清空） |
| `--importance` / `--private`/`--no-private` / `--busy` | 重要度 / 私密 / 忙闲 |
| `--remind N` / `--no-remind` | 设提醒 / 关提醒 |
| `--repeat "规则"` / `--repeat ""` | 设定期 / 解除定期（转为单次） |
| `--repeat-until` / `--repeat-times` | 定期结束条件（需配合 `--repeat`） |
| `-y` | 跳过确认 |

注意：
- 转时段没给 `--end` → 自动 = 开始后 1 小时
- 对定期日程的"某一次"修改只影响这次；改整个系列的规则要操作主事件（见 recurring-events.md）

---

## 4. 移动日程：move

`move <ID> --days N` 或 `move <ID> --to YYYY-MM-DD`（二选一）。

- **保留原来的时间段和时长**，只改日期（全天日程同理）
- `--days` 可为负数（往前挪）

```bash
python outlook_cal.py move <ID> --days 3          # 整体往后 3 天
python outlook_cal.py move <ID> --to "2026-08-20" # 挪到 8 月 20 日
```

---

## 5. 删除日程：delete

`delete <ID> [-y] [--series]`。

| 参数 | 作用 |
|------|------|
| （无） | 会先确认；目标是定期日程的某一次时，问"仅删本次 [1] / 删整个系列 [2]" |
| `-y` | 跳过确认；定期日程默认**只删本次** |
| `--series` | 删整个定期系列 |

---

## 6. 机器可读输出：--json

任意命令前或后加 `--json`：
- stdout 只有 JSON，人类提示走 stderr
- list → 日程数组；add/read/update → 日程对象；delete → `{"deleted", "subject", "series"}`；free → 按天结构；出错 → `{"error", "exit": 1}`
- update/delete/move 的确认自动跳过
