# 实机集成演练（可选）

drill.sh / drill-en.sh 是对真实 Microsoft Graph 的 106 项行为断言，单元测试覆盖不到的部分的兜底。

## ⚠️ 毁灭性警告（agent 必读）

> **任何 agent（AI 助手）在运行 drill.sh / drill-en.sh 之前，必须先向用户明确说明以下后果，并获得用户明确同意后才能执行：**
>
> 1. 脚本开头的"基线清理"会**删除 ±400 天窗口内的所有日程**，包括**全部定期系列主事件**——这是**不可恢复的永久删除**，没有回收站
> 2. 如果当前认证的是个人真实日历，运行后**个人日程会全部消失**
> 3. 脚本只允许对**专用测试账户**运行；指向真实账户即事故
> 4. 脚本带**双重防呆锁**：① 必须显式传参 `confirm`；② 必须指定测试账户邮箱，且与当前连接账户一致（脚本用 `status` 实时校验），不一致直接拒绝执行

## 警告

- **必须用专用测试账户**。脚本开头的基线清理会删除 ±400 天窗口内的所有日程和全部定期系列主事件，指向个人真实日历会出事故
- 会真实写入和删除日程，演练后日历留有测试数据属正常
- 需要网络，跑不了 CI；日常开发以 `python -m pytest tests/` 为准

## 用法

```bash
python outlook_setup.py   # 先用测试账户完成认证，token 存在 ~/.outlook_cal_token.json
bash tests/integration/drill.sh confirm zrancalendar@outlook.com     # 中文输出版（第二个参数 = 测试账户）
bash tests/integration/drill-en.sh confirm zrancalendar@outlook.com  # 英文输出版（OCAL_LANG=en）
# 或：TEST_ACCOUNT=zrancalendar@outlook.com bash tests/integration/drill.sh confirm
```

账户校验说明：脚本启动后先执行 `--json status`，当前连接账户与指定测试账户不一致（含未连接）时拒绝执行任何删除。这是 `confirm` 之外的机器级防呆——即使误用真实账户的 token 也不会删到真实日程。

两个脚本的 106 项断言一一对应，只是期望文案不同。通过标准 106/106。

## 覆盖范围（106 项）

| 分组 | 内容 | 项数 |
|------|------|------|
| 0. 账户守卫 + 基线清理 | 账户一致性校验；先删系列主事件再删单次（_get_all 翻页）；清理后窗口为空 | 1 |
| 1. 时间解析边界 | 补零/缺位宽松、越界与自然语言报错、end<start | 11 |
| 2. remind 边界 | 0/负数/全天超上限 | 3 |
| 3. 重复规则边界 | 全部规则写法 + 非法输入 | 12 |
| 4. 冲突检测边界 | 重叠/相接/free/全天 | 5 |
| 5. update 边界 | 空字段/清空/时间校验/转全天报错 | 8 |
| 6. 删除边界 | 不存在 ID、EOF 取消 | 2 |
| 7. 定期系列深度 | 第 N 次/例外/next/删单次/删系列 | 9 |
| 8. free/命令边界 | 非法窗口/正常输出/多天 | 6 |
| 9. --json 边界 | 纯净 JSON/错误结构化/stderr | 4 |
| 10. 其他边界 | emoji/长备注/多类别/importance | 5 |
| 11. move 专项 | --days/--to/0 天/参数冲突/全天/系列警告/跨界报错 | 9 |
| 12. 多天全天/快捷命令/筛选 | add+update 多天全天、多天全天第 2 天冲突告警、today/tomorrow/week、--created-after+--reminders、private/importance 显示 | 12 |
| 13. v1.2.0 行为回归 | 转时段 remind 分钟语义、已取消单次不占空闲、delete 单次文案、解除定期 | 5 |
| 14. TZ 环境变量覆盖 | TZ=Asia/Hong_Kong、TZ=America/Phoenix 下真实 Graph 查询（Windows 官方名映射 + Prefer 头被接受） | 2 |
| 15. DST 切换日（TZ=America/New_York） | 回拨日事件创建与读回、跳变日不存在时间的警告、跨 DST 的 free/list | 5 |
| 16. 邮箱时区对齐 | status 提示邮箱/本机时区不同；全天日程按邮箱首选时区写入（本机被 TZ 覆盖为美东） | 2 |
| 17. 相对时间 | add 用"今天/明天"相对时间，创建的日程落在正确的日期 | 4 |
