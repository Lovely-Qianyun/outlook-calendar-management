# 实机集成演练（可选）

drill.sh / drill-en.sh 是对真实 Microsoft Graph 的 64 项行为断言，单元测试覆盖不到的部分的兜底。

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
