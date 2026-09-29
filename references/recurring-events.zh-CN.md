# 定期日程

为例会、生日或周期性提醒创建重复系列，也可以单独调整其中一次。例如，“从 2026 年 9 月 30 日开始，每周三 09:00–09:30，共八次”会在 Outlook 中生成一个包含八次会议的系列。

## 创建一个每周重复的系列

先按[快速开始](../README.zh-CN.md#快速开始)安装并登录。在项目根目录新建 UTF-8 文件 `weekly.json`，内容如下：

```json
{"type":"weekly","interval":1,"daysOfWeek":["wednesday"],"firstDayOfWeek":"monday"}
```

运行下面的命令会写入真实日历；请按需替换日期、时区、标题和次数：

```bash
python scripts/outlook_cal.py add "周会" "2026-09-30 09:00" "2026-09-30 09:30" --repeat-file weekly.json --repeat-times 8 --timezone Asia/Shanghai --json
python scripts/outlook_cal.py list --from 2026-09-30 --days 14 --timezone Asia/Shanghai --json
```

第一条命令返回系列主事件，含 `id` 和 `recurrence`；第二条查询会展开该窗口内的出现。在没有其他日程的日历中，可看到 9 月 30 日和 10 月 7 日两次周会。`weekly.json` 是本地输入文件，创建结果保存在 Outlook，JSON 结果显示在终端。

## 选择规则与结束条件

`--repeat-file` 读取规则对象本身；也可通过 `--repeat` 直接传入 JSON。文件格式可减少 shell 引号转义问题。支持以下六种类型：

| 用户要求 | JSON 规则 |
|----------|-----------|
| 每 2 天 | `{"type":"daily","interval":2}` |
| 每周五 | `{"type":"weekly","interval":1,"daysOfWeek":["friday"],"firstDayOfWeek":"monday"}` |
| 每 2 周的周一、周三 | `{"type":"weekly","interval":2,"daysOfWeek":["monday","wednesday"],"firstDayOfWeek":"monday"}` |
| 每周一至周五 | `{"type":"weekly","interval":1,"daysOfWeek":["monday","tuesday","wednesday","thursday","friday"],"firstDayOfWeek":"monday"}` |
| 每 3 个月的 15 日 | `{"type":"absoluteMonthly","interval":3,"dayOfMonth":15}` |
| 每月最后一个周五 | `{"type":"relativeMonthly","interval":1,"index":"last","daysOfWeek":["friday"]}` |
| 每年 9 月 21 日 | `{"type":"absoluteYearly","interval":1,"month":9,"dayOfMonth":21}` |
| 每年 11 月最后一个周三 | `{"type":"relativeYearly","interval":1,"month":11,"index":"last","daysOfWeek":["wednesday"]}` |

每种类型需要上表示例中对应的全部字段。字段条件如下：

- `interval` 为 1–2,147,483,647 的整数；`dayOfMonth` 为 1–31；`month` 为 1–12。按年重复的月日组合须有效，允许 2 月 29 日。
- `daysOfWeek` 为非空、无重复的小写英文星期数组；`weekly` 还需要 `firstDayOfWeek`，值为 `monday` 至 `sunday`。
- 相对月度/年度规则的 `index` 为 `first`、`second`、`third`、`fourth` 或 `last`。多个星期候选表示选取该月最早满足规则的日期，每月只生成一次。
- 文件直接包含 pattern 字段，所有键唯一且属于所选类型。小时重复和按工作日数量计算间隔不在这些规则的支持范围内。

指定规则时，可附带一种结束条件：

| 选项 | 含义 |
|---|---|
| `--repeat-times 8` | 共八次，次数范围为 1–2,147,483,647。 |
| `--repeat-until 2026-12-31` | 截止日期含当天，且不早于开始日期。 |
| 两者均省略 | 持续重复，无截止日期。 |

## 修改一次或整个系列

按发生日期查询的 `list` 会返回展开后的单次出现。用该项 `id` 操作一次；通过 `read` 中的 `seriesMasterId` 获取主事件 ID，操作系列规则。主事件本身的 `id` 也可作为系列目标。

| 需求 | 命令（省略解释器和脚本路径） | 使用条件与结果 |
|---|---|---|
| 修改某次时间 | `update <单次ID> --start "2026-10-07 10:00" --end "2026-10-07 10:30" --timezone Asia/Shanghai --json` | 该次成为例外；新时间须处于相邻出现允许的边界内。 |
| 删除某次 | `delete <单次ID> --json` | 只删除该次，之后用 `list` 核实。 |
| 修改整个系列规则 | `update <主ID> --repeat-file weekly.json --repeat-times 8 --json` | 可能重置单独修改或删除过的出现，操作前应确认这一影响。 |
| 解除重复 | `update <主ID> --repeat= --json` | 移除重复规则，保留为单个日程。 |
| 删除整个系列 | `delete <主ID> --json` 或 `delete <单次ID> --series --json` | 删除系列中的全部出现。 |
| 查看下次出现 | `next <单次ID或主ID> --json` | 在未来 365 天内查询。 |
| 将整个系列挪动一天 | `move <主ID> --days 1 --json` | 操作对象为整个系列。 |

**更新规则会重建结束条件。** 需要保留原截止日期或次数时，先读取原 `recurrence.range`，再明确传入 `--repeat-until` 或 `--repeat-times`；均省略将变为无截止。`--json` 会跳过终端确认，运行前应已确定目标和范围。

修改后用 `read` 核对规则、结束条件及时间，必要时用 `list` 查看展开结果。删除时，在同一已核实账户下，将返回的 `deleted` ID 和 `series` 标记与目标范围核对。单次删除通过发生日期窗口核实目标缺席；整系列删除还需回读保留的主事件 ID，取得明确的日程不存在结果。仅窗口为空不足以证明系列已删除；验证出错时保留未确定状态，考虑再次写入前先按[写入结果恢复流程](troubleshooting.zh-CN.md#写入结果不明时)处理。

字段格式见[命令参考](commands.zh-CN.md)，规则模型见 [Microsoft Graph recurrencePattern](https://learn.microsoft.com/en-us/graph/api/resources/recurrencepattern?view=graph-rest-1.0)。
