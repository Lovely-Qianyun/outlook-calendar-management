# 输出协议评估

检查助手和脚本能否从输出中读取正确的 ID、时间、空闲区间和错误。例如，创建日程发生冲突时，stdout 中应是新日程结果，stderr 中是冲突提示；解析者得到的是新日程 ID。

## 运行与查看结果

在项目根目录运行离线回归，网络和依赖安装调用由测试模拟：

```bash
python -m pip install pytest requests msal tzdata
python -m pytest tests/test_protocol.py -q
```

测试摘要显示在终端；加 `--junitxml=protocol-results.xml` 可保存报告到当前目录。要检查助手如何提取结果，在全新会话中用模拟工具运行下方用例，并手工记录提取值及预期值。建议保存到已创建的 `.local-calendar-test/protocol-results.md`，与自动测试报告分开。

优先解析 `--json` 的字段。文本模式的锚点和缩进也属于当前输出约定，供已有调用方使用。

## 文本输出的提取格式

| 信息 | 正则 | 说明 |
|------|------|------|
| list 的 🆔 | `^    🆔 (.+)$` | 4 空格缩进 |
| add 的 🆔 | `^   🆔 (.+)$` | 3 空格缩进 |
| read 的 🆔 | `^🆔 (.+)$` | 顶格 |
| 系列主事件 ID | `^🆕 .+?: (.+)$` | 锚点+冒号结构，顶格；冒号前文案随语言（zh: 系列主事件ID / en: Series master event ID） |
| free 时段 | `(\d{2}:\d{2})-(\d{2}:\d{2})` | 逐段 HH:MM-HH:MM；无时段列表 = 整天空闲或无空闲（区分依赖文案或 `--json`） |
| --json 错误 | `{"error": ..., "exit": 1}` | stdout 可 json.loads |

## 输出约定

1. **事件 ID 必须来自命令结果**：JSON 的 `id` / `seriesMasterId`，或上述 stdout 的 🆔 / 🆕 行
2. **stdout 里的 🆔 只能属于结果事件**：冲突警告等非交互提示（含现有日程的 🆔）一律在 stderr
3. 锚点（🆔/🆕/✅/⚠️…）与**结构**（缩进/冒号/括号/时段格式）与语言无关，zh/en 完全一致；`--json` 字段名也与语言无关
4. **自然语言文案不属于协议**：行内文案（如"系列主事件ID / Series master event ID"、"确认? / Confirm?"）随语言自由翻译，agent 提取信息只依赖锚点与结构，不依赖具体文案
5. `--json` 模式下每次操作向 stdout 输出且只输出一个 JSON 值，人类提示全部在 stderr。`--help` 仍显示文本帮助；`--json` 未指定命令时返回结构化参数错误。参数、命令及依赖启动错误使用 `{"error": ..., "exit": 1}`；`status` 未连接时保留连接状态对象。
6. Graph/网络错误可附加与语言无关的 `code`、`http_status`、`outcome_unknown`，见[命令参考](../references/commands.zh-CN.md)。缺少元数据不代表可以安全重试。
7. JSON 使用 ASCII 转义，确保 Unicode 日程内容和错误信息经过 Windows GBK 管道后，`json.loads` 仍能完整还原。

## 评估用例

对每条用例，在全新会话里让 agent 执行操作并提取信息，核对提取结果。

用例 9 的 `wednesday.json` 是 UTF-8 文件，内容为以下明确的 pattern 对象：

```json
{"type":"weekly","interval":1,"daysOfWeek":["wednesday"],"firstDayOfWeek":"monday"}
```

| # | 操作 | 期望提取 |
|---|------|--------- |
| 1 | `list --from 2026-08-20 --days 7`，输出 3 条日程 | 3 个 🆔（4 空格行），与输出一一对应 |
| 2 | `add "周会" "2026-08-20 15:00" "2026-08-20 16:00"`（与现有日程冲突） | 新日程的 🆔（3 空格行） |
| 3 | `read <某次出现ID>` | 该次 🆔 + 🆕 行主事件 ID（锚点+冒号结构）两个值 |
| 4 | `free "2026-08-21" --from 09:00 --to 18:00` | 空闲时段列表（HH:MM-HH:MM）；无时段列表 = 整天空闲或无空闲 |
| 5 | `delete <ID> -y` 单次日程 | stdout 有删除成功行（🗑️ 锚点），无残留 ID |
| 6 | 任意操作 `--json`（文本帮助除外） | stdout 直接 json.loads 成功 |
| 7 | `add "坏时间" "无效日期"` 出错 | stderr 有 ❌；stdout 为空 |
| 8 | 英文环境（`--lang en`）跑 1-5 | 锚点与中文环境完全一致 |
| 9 | 定期系列：`read` 某次 → `update <主ID> --repeat-file wednesday.json`，文件为明确的 weekly pattern | 主 ID 来自 🆕 行，而不是某次 ID |
| 10 | `next <系列ID>` | 下次出现的 🆔（4 空格行） |
| 11 | 用户要求今天 14:00–15:00；先 `context --json`，再用已确定的绝对开始/结束和命名时区执行 `add` | 输出日期与本次规范化所用的上下文日期一致；后续验证/重试复用相同参数 |
| 12 | 中英文执行 `move <单次或主事件ID> --days 1 --json`，包括模拟 PATCH 失败 | 成功时为含目标 ID 和移动后日期的一个事件对象；失败时为一个错误对象。两种情况下定期日程提示都在 stderr。 |
| 13 | 中英文执行 `update <ID> --json`，不提供修改字段 | 一个 `{"error": ..., "exit": 1}` 对象，退出码 1；未发送 PATCH |
| 14 | `--json read` 缺少 ID、`list --days` 值非法、未知命令或模拟依赖安装失败 | 一个错误对象，退出码 1；安装诊断仍在 stderr |
| 15 | 中英文执行 `read <ID> --json` 并经 GBK 管道，日程含中文/emoji 或模拟 Unicode 错误 | `json.loads` 逐字还原；ASCII 转义是正常格式 |
| 16 | 中英文执行 `read <主ID> --json`，分别模拟日程不存在、认证失败、权限失败及其他 404 | 通过 `code` 与 `http_status` 区分；仅 `event_not_found` / 404 支持目标缺席判断。 |
| 17 | 中英文创建超时，或模拟写入服务端错误、无法解析的成功响应 | 单一 JSON 错误保留 `error`、`exit`，并携带 `outcome_unknown: true`；创建/修改不自动重发。 |

## 判定

目标为 17/17。用例 12–15 也由 `test_protocol.py` 离线覆盖。失败记录应包含实际 stdout、stderr、退出码及提取结果；调整输出格式时同步维护测试和本页约定。
