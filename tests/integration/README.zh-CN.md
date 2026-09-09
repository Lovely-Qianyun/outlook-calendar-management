# 可选的真实日历冒烟测试

`drill.py` 通过日历 CLI 调用 Microsoft Graph。它创建两个带唯一主题的测试日程（其中一个是重复两次的系列），读取和修改它们，最后只删除本次创建成功返回的 ID。脚本不会清空账号，也不会删除搜索结果中的其他日程。建议使用专用测试账号。

日常运行 `python -m pytest tests/` 全部是离线测试，也包含该脚本的模拟客户端测试。不要把真实冒烟测试放进日常自动验证流程。

## 显式运行

先连接准备使用的测试账号。如需保留已有连接，请在同一终端中先将 `OCAL_TOKEN_PATH` 设为独立的令牌文件路径，再登录并测试；详见[配置说明](../../references/configuration.zh-CN.md)。测试脚本的子进程会继承该设置。

```text
python scripts/outlook_setup.py
python tests/integration/drill.py --account test@example.com --confirm
python tests/integration/drill.py --account test@example.com --confirm --lang zh
```

将 `test@example.com` 替换为当前连接的日历账号。写入必须同时提供 `--account` 和 `--confirm`。脚本在每次写入和每次清理删除前，通过 `status --json` 核对实际账号；账号不匹配就停止该操作。`--lang` 决定底层 CLI 的输出语言，最终报告始终使用相同的 JSON 字段。

所有命令都以 Python 子进程参数列表运行，Windows 不需要 Bash。日期使用明确值，定时日程同时提供起止时间，重复规则使用 JSON，时区统一为 UTC。测试日期从当前 UTC 日期之后 30 天开始。固定的三天查询窗口覆盖预期的两个重复日期及额外一天，用于发现多余实例。测试日程标为空闲，主题带唯一的 `ocal-smoke-...-` 前缀。

## 覆盖内容和结果

脚本检查 `context`、确定性的 `date` 日期加减、定时日程 `add` 和 `read`、主题 `update`、按明确日期 `move`、明确时间窗口的 `list`、`free` 返回结构，以及每日重复规则创建。它核对日程读取结果、系列规则，以及恰好两个展开实例的起止时间。清理后查询固定测试窗口，确认已知日程 ID 及以其为 `seriesMasterId` 的实例均已消失。详细参数校验、夏令时边界、其他重复模式、空闲时段计算正确性和错误情况由离线测试覆盖。

退出码为 0 且报告 `"ok": true` 表示检查和清理均成功。失败报告包括：

- `errors`：失败的检查或清理操作。
- `remaining_ids`：本次创建后，尚未确认删除成功的 ID。
- `deletion_checks`：删除后的回查状态：`absent`（窗口内已消失）、`present`（仍存在）或 `unverified`（未能核实）。
- `unknown_create_subjects`：创建请求未返回可用 ID 的唯一主题；这些请求的结果可能未知。
- `unknown_create_checks`：在固定窗口内按完整主题只读回查的结果：`observed`（查到匹配）、`not_found`（未查到）或 `unverified`（未能核实），并附匹配 ID 和时间。查得的 ID 不会加入自动清理。
- `test_window`：上述检查使用的固定日期范围和时区。
- `subject_prefix`：供人工检查的本次运行标识。

检查失败后仍会执行清理。清理只处理本次创建返回的 ID，并在每次删除和诊断查询前重新核对账号。脚本不会自动重试超时、响应格式错误等结果不明的写入；删除后回查失败也不会再次发起删除。创建未返回 ID 时，会按完整主题只读查询并报告观察结果，不重发创建，也不删除查得的 ID。`not_found` 只表示固定窗口内未查到，不能证明写入从未发生。再次运行前，请在预期账号中检查报告中的未解决项目。强制终止进程可能导致清理无法执行，可以用唯一主题前缀查找遗留的测试数据。
