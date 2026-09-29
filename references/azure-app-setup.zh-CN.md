# 使用自己的 Azure 应用

需要自行管理应用注册和授权时，可以将自有应用的客户端 ID 传给登录脚本。例如，注册一个供个人 Outlook 账户使用的公共客户端，登录后即可通过同一套日历命令操作账户。常规连接可直接使用[内置应用](configuration.zh-CN.md)。

## 注册和配置

需要能在 Microsoft Entra 租户中注册应用的账户或管理员协助。在 [Microsoft Entra 管理中心](https://entra.microsoft.com/)进入“应用注册”，创建应用并记录 **Application (client) ID**；账户类型按使用者选择，具体入口见[微软应用注册指南](https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app)。

1. 为应用命名。仅供个人 Outlook.com 使用时，选择个人 Microsoft 账户；组织账户需要匹配的组织账户支持和管理员许可。当前登录脚本使用 `consumers` / `common` 入口，没有租户 ID 参数，组织应用配置需与此相符。
2. 在身份验证设置中启用 **Allow public client flows（允许公共客户端流）** 并保存。本工具采用设备码流程，适用于公共客户端，参见[微软公共客户端说明](https://learn.microsoft.com/en-us/entra/identity-platform/msal-client-applications)。
3. 在 API 权限中添加 Microsoft Graph 的**委托权限** `Calendars.ReadWrite` 和 `MailboxSettings.Read`。用途见[连接配置](configuration.zh-CN.md)。按组织策略完成所需的管理员同意。

此登录流程使用客户端 ID 和用户交互授权，无需创建客户端密钥。

## 登录并查看结果

完成[快速开始](../README.zh-CN.md#快速开始)中的依赖安装后，在项目根目录运行，将占位值替换为应用客户端 ID：

```bash
python scripts/outlook_setup.py YOUR_CLIENT_ID
python scripts/outlook_cal.py status --json
```

按终端设备码提示完成登录。`status` 应返回 `connected: true` 及预期账户。凭据保存到 `OCAL_TOKEN_PATH` 指定位置，默认是 `~/.outlook_cal_token.json`；成功登录会替换该路径中的已有连接。

## 连接失败时

| 现象 | 检查项 |
|---|---|
| 找不到应用或账户类型不匹配 | 客户端 ID、应用支持的账户类型、公共客户端设置和组织限制。 |
| 403 权限错误 | 委托权限及同意状态；日历操作需要 `Calendars.ReadWrite`，邮箱时区读取需要 `MailboxSettings.Read`。 |
| 设备码过期 | 重新运行同一登录命令，使用新的设备码。 |

其他问题见[故障排查](troubleshooting.zh-CN.md)。
