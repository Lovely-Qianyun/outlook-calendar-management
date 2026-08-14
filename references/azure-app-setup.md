# 自带 Azure APP 注册指南

> 只在你**不用内置默认应用**、想用自己的 Azure 应用时阅读。其余情况跳过本节。

## 为什么需要 Client ID

- **Client ID（应用程序 ID）**：你的应用在微软身份体系里的唯一标识。设备码登录只需要它。
- **不需要 Tenant ID / Client Secret**：那两样是"服务器后台无人工交互"场景（机密客户端）才用的。本工具是公共客户端 + 设备码流程，任何界面让你填这两样的，直接忽略。

## 注册步骤

1. 打开 https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade
2. 用 Outlook 账户登录
3. **新建注册** → 填写自己的应用名称→ 账户类型选 **"仅个人 Microsoft 帐户"**
4. **身份验证** → 添加平台 → **"移动和桌面应用程序"** → 勾选 `https://login.microsoftonline.com/common/oauth2/nativeclient`
5. 身份验证页底部 → **"允许公共客户端流"** → 设为 **"是"** → 保存
6. **API 权限** → 添加权限 → Microsoft Graph → 委托权限 → 搜索并添加两个权限：
   - `Calendars.ReadWrite`（日程读写，必需）
   - `MailboxSettings.Read`（读取邮箱首选时区——全天日程按邮箱时区写入需要它；不加则全天日程退回按本机时区写）
7. 回到 **概览** 页，复制顶部 **"应用程序(客户端) ID"**

## 认证

```bash
python outlook_setup.py <你的Client ID>
```

之后的流程与默认应用完全一样：脚本打印验证码 → 浏览器打开 `https://www.microsoft.com/link` 输入 → Outlook 账户授权。token 自动续期。

## 常见失败

| 症状 | 原因与解决 |
|------|-----------|
| 设备码报"找不到应用" | 账户类型没选"个人 Microsoft 帐户"，或"允许公共客户端流"没开启 |
| 403 Forbidden | `Calendars.ReadWrite` 委托权限没加；`status` 不显示邮箱时区、全天日程退回本机时区时检查 `MailboxSettings.Read` 是否已加 |
| 验证码过期 | 重新运行 `python outlook_setup.py` 再试一次 |
