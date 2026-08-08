# 实机集成演练（可选）

drill.sh / drill-en.sh 是对真实 Microsoft Graph 的 64 项行为断言，单元测试覆盖不到的部分的兜底。

## ⚠️ 毁灭性警告（agent 必读）

> **任何 agent（AI 助手）在运行 drill.sh / drill-en.sh 之前，必须先向用户明确说明以下后果，并获得用户明确同意后才能执行：**
>
> 1. 脚本开头的"基线清理"会**删除 ±400 天窗口内的所有日程**，包括**全部定期系列主事件**——这是**不可恢复的永久删除**，没有回收站
> 2. 如果当前认证的是个人真实日历（如本例的 Qianyun-Calendar@outlook.com），运行后**个人日程会全部消失**
> 3. 脚本只允许对**专用测试账户**运行；指向真实账户即事故
> 4. 脚本从 v1.1.0 起需要显式传参 `confirm` 才会真正执行删除（防呆锁）：`bash tests/integration/drill.sh confirm`

## 警告

- **必须用专用测试账户**。脚本开头的基线清理会删除 ±400 天窗口内的所有日程和全部定期系列主事件，指向个人真实日历会出事故
- 会真实写入和删除日程，演练后日历留有测试数据属正常
- 需要网络，跑不了 CI；日常开发以 `python -m pytest tests/` 为准

## 用法

```bash
python outlook_setup.py   # 先用测试账户完成认证，token 存在 ~/.outlook_cal_token.json
bash tests/integration/drill.sh      # 中文输出版
bash tests/integration/drill-en.sh   # 英文输出版（OCAL_LANG=en）
```

两个脚本的 64 项断言一一对应，只是期望文案不同。通过标准 64/64。
