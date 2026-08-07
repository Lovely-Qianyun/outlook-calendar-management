# 第一次连接日历

## 连接步骤（约 2 分钟）

```bash
pip install msal requests tzdata   # tzdata 仅 Windows 需要
python outlook_setup.py            # 无参数 = 内置默认应用
```

1. 脚本打印一个**验证码**
2. 浏览器打开 `https://www.microsoft.com/link`，输入验证码
3. 用你的 Outlook 账户（微软账户）登录并授权
4. 完成 → 之后**自动续期，不用再认证**

**确认成功**：`python outlook_cal.py status` 显示"✅ 已连接到 Outlook 日历"。

> 手机、电脑、网页上看到的是同一个日历——连接后所有操作实时同步。

## 换账户 / 重新连接

重新运行 `python outlook_setup.py` 即可用另一个账户授权（会覆盖当前连接）。
登录失效时（报 invalid_grant / 401）也这样做。

## 想用自己的 Azure 应用？

默认开箱即用，一般不需要。想注册自己的应用（比如为了安全隔离）：见 `azure-app-setup.md`。
只需要注册后复制 **Client ID** 一个参数：`python outlook_setup.py <你的Client ID>`。
