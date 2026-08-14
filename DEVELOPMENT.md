# 开发者说明

面向 skill 维护者：代码结构、协议、设计决策、测试方法。
写这份文档的目标是让开发者不读代码或少读代码就能明白系统怎么运转，
也让下一代开发者可以用 agent 直接基于本文档开发，不用逆向工程。

## 文件结构

```
scripts/
  outlook_cal.py        # 入口：解析命令行、分发到各命令；预扫 --lang 让帮助文本按语言渲染
  outlook_setup.py      # 认证：设备码流程；main() 守卫，import 不触发流程，_box 可单测
  ocal_errors.py        # CalError：抛给用户的错误
  ocal_bootstrap.py     # 首次运行依赖自检与自动安装 requests/msal/tzdata；自身只依赖 stdlib
  ocal_i18n.py          # 多语言：语言解析 + 字符串表 + 日期/星期格式化
  ocal_auth.py          # token 获取与续期，用 msal
  ocal_time.py          # 时区探测与时间解析，模块加载时算好 LOCAL_TZ
  ocal_graph.py         # Graph API 请求、重试、翻页
  ocal_recurrence.py    # 定期规则：解析、格式化、第 N 次计算
  ocal_events.py        # 全部命令实现、显示、冲突/空闲计算

tests/
  conftest.py           # pytest 公共配置：脚本目录进 sys.path、语言状态复位
  test_time.py          # 时间解析/时区/全天范围
  test_recurrence.py    # 定期规则解析/格式化/第 N 次
  test_i18n.py          # 语言解析/字符串表完整性/日期星期格式化
  test_events.py        # 纯函数 + mock 网络层的命令路径
  test_graph.py         # 请求重试与错误映射，mock requests
  test_auth.py          # token 文件读写与续期，mock msal
  test_protocol.py      # 输出协议解析：agent 提取正则逐条钉住（🆔 缩进/时段格式/stdout 纯净性）
  trigger-eval.md       # 触发评估集：改 description 时对照验证触发/不触发
  protocol-eval.md      # 输出协议评估集：新会话里端到端验证提取规则，11/11
  integration/          # 可选：真实账户实机演练，需专用测试账户，见其 README
    drill.sh            # 106 项行为断言，中文输出
    drill-en.sh         # 同上，英文输出
    README.md           # 用法与警告

.github/workflows/
  tests.yml             # CI：三平台（Linux/Windows/macOS）× Python 3.10/3.13 跑离线测试

references/             # 用户文档
  commands.md           # 命令完整参考
  recurring-events.md   # 定期日程专题
  configuration.md      # 连接配置
  troubleshooting.md    # 故障排除
  azure-app-setup.md    # 自带 Azure 应用注册
```

## 运行前提

- `scripts/` 目录整体分发，入口和全部 `ocal_*.py` 必须在一起
- 依赖 requests、msal、tzdata，通常不用手动装，首次运行会自动 pip 安装，见依赖自检
- 第一次使用先跑 `python outlook_setup.py` 完成设备码认证

## 版本号规则

`version` 是 x.y.z 三段，各段何时 +1：

| 段  | 什么时候 +1                                             |
| --- | ------------------------------------------------------- |
| x   | 破坏性变更：命令不兼容、配置格式变化、行为协议改变      |
| y   | 新功能或行为变化：新增命令/参数、输出文案变化、依赖变化 |
| z   | 纯维护：bug 修复、注释重构，行为不变                    |

## 改动约定

- 改输出前先读输出协议章节，想清楚会不会破坏下游解析；zh/en 文案被测试逐字钉住，改动需同步更新两语言断言并 bump y 版本号，不随意改；每周周五这类既有显示习惯也照旧，不要修正
- 重构后跑回归，见测试；离线单测全绿 +（改到协议时）实机 106/106 才算过
- 新增行为时同步更新 tests/ 的断言，两个语言版本都要；输出格式变更必须同步 tests/protocol-eval.md 和 test_protocol.py

## 依赖自检

- `ensure_deps()` 必须在导入 `ocal_events` 之前调用，导入顺序约束的完整解释见关键设计决策
- `tzdata` 是 Windows 时区正确的关键，缺失会静默回退 UTC 导致时间偏几小时，见关键设计决策的时区小节
- bootstrap 自身只准用 stdlib + ocal_i18n，提示文案走 t() 的 deps_* 键

## 多语言约定

- print / CalError / input 提示这类用户可见文案都走 `ocal_i18n.t()`，不硬编码中文
- 语言优先级：`--lang` 参数 > `OCAL_LANG` 环境变量 > 系统语言检测，中文系统用 zh，其余用 en
- emoji 锚点 🆔/✅/⚠️/🆕 等是输出协议的一部分：🆔 行就是事件 ID，脚本和 agent 都从它提取，两种语言共用，绝不翻译；`--json` 输出语言无关
- 日期/星期用 `d_md`/`date_weekday`/`weekday` 这类运行时函数。语言在模块导入后才确定，不能做成常量
- 新文案必须同时填 zh/en 两张表；缺键会回退中文再回退键名，开发期一眼看出漏翻

## 输出协议：字符串协议

命令的人类可读输出是一套稳定协议，agent 和脚本都靠它解析结果。协议的意义是：拿到任意一段输出，不读代码就知道每行是什么意思、ID 在哪一行。改输出前先对照本节，想清楚会不会破坏下游解析。

### emoji 锚点

| 锚点 | 含义 | 出现位置 |
|------|------|----------|
| 🆔 | 事件 ID | list 每条一行，add/read 结果区 |
| 🆕 | 系列主事件 ID | read 的定期系列上下文 |
| ✅ ⚠️ ❌ ℹ️ | 成功 警告 错误 提示 | 各命令结果 |
| 🔁 | 定期标记 | list 行尾，read 系列上下文 |
| 📅 🕐 📌 | 日期 时间 全天 | 列表与详情 |
| 📍 🏷️ ⏰ 🔒 📊 📝 🔗 🕘 👤 | 地点 类别 提醒 私密 忙闲 备注 链接 添加时间 组织者 | read 详情 |
| 🚫 | 用户取消 | 确认流程 |

### 固定规则

1. 🆔 行是事件 ID 的唯一来源，agent 从它提取，绝不猜测或编造
2. 锚点是语言无关的，zh/en 输出完全一致，绝不翻译
3. 🆔 行缩进是稳定的：list 里 4 空格，add 里 3 空格，read 顶格。drill 脚本用 sed 按缩进抓 ID，动缩进等于破坏回归测试
4. 错误统一 ❌ 前缀加友好文案，退出码 1；--json 模式下输出 {"error": ..., "exit": 1}
5. 确认提示固定 确认? [y/N]，接受 y/yes；delete 的系列选择接受 2/系列/s/series
6. --json 模式 stdout 只输出 JSON，人类提示全部走 stderr；非 --json 模式下，**非交互路径的提示/警告**（冲突警告、全天自动提示、解除/重置定期警告、无字段更新提示）也一律走 stderr——stdout 只保留结果、🆔 协议行与交互确认对话。冲突警告里带现有日程的 🆔，进 stdout 会让 agent 分不清哪个 🆔 是新日程

### 行结构

- list 每条占两行：`    {图标} {时间}  {标题}{定期标记}{类别}`，下一行 `    🆔 {ID}`
- 定期标记是 🔁 加括号后缀：`(系列)`、`(已修改)`、`(已取消)`，系列主事件行尾还带规则描述
- read 的 ID 行：`🆔 {ID}`；系列上下文：`🆕 系列主事件ID: {ID}`
- free 每行：`📅 {日期} {星期}：{时段列表} 空闲`，时段格式 HH:MM-HH:MM

### 时间与日期

- 时间固定 MM/DD HH:MM，数字格式两种语言一致
- 日期 08月10日 / 08/10，星期 周一 / Mon，全天 / All day，日期范围 ~ / -
- 定期描述：每天 / 每N天 / 每周X / 每N周X / 每月N日 / 每月第N个周X / 每年X月X日，结束条件后缀（共N次）/（至日期）

## 测试

### 单元测试：日常开发主入口

离线跑，网络全部 mock 掉，CI 可用：

```bash
python -m pytest tests/          # 需要 pytest
python -m py_compile scripts/*.py
```

覆盖：时间解析边界、定期规则全部写法与非法输入、i18n 字符串表完整性，即脚本里每个 t() 调用键都必须同时存在于 zh/en 两张表、冲突/空闲计算、Graph 重试与错误映射、token 续期与跨进程锁、邮箱时区回退、DST 跳变检测、输出协议解析（test_protocol.py），以及 mock 掉网络的各命令路径。

CI：`.github/workflows/tests.yml` 在 Linux/Windows/macOS × Python 3.10/3.13 上跑同一套离线测试——时区探测链、跨平台路径、编码降级都靠它兜底。

注意：`outlook_setup.py` 的 main() 有守卫，import 不会触发设备码流程，那是网络轮询，别误当死循环。

### 触发评估：改 description 用

description 决定 skill 何时被触发，改它之前先跑一遍 `tests/trigger-eval.md`：
12 条应该触发的请求和 6 条不该触发的请求，在全新会话里逐条验证。
漏触发补关键词，误触发加排除条件，标准是 12/12 和 6/6。

### 协议评估：改输出格式用

输出格式是 agent/脚本解析的契约，改它之前跑一遍 `tests/protocol-eval.md`：
11 条"从输出提取 🆔/时段/错误"的端到端用例，在全新会话里逐条验证；
同一套正则已被 `test_protocol.py` 自动化钉住。标准是 11/11。

### 实机集成演练：可选

单元测试验证不了真实 Graph 的行为，`tests/integration/` 里有两份 106 项断言脚本兜底。**必须用专用测试账户**，脚本开头的基线清理会删 ±400 天窗口内的日程，别指向个人真实日历。用法见 `tests/integration/README.md`。

> ⚠️ **agent 必读**：运行 drill.sh / drill-en.sh 前，必须先向用户明确提示：脚本会**永久删除 ±400 天窗口内的全部日程和全部定期系列主事件**（不可恢复），并取得用户明确同意后才能执行；只允许对专用测试账户运行。脚本带双重防呆锁：必须传 `confirm` 参数，且必须指定测试账户邮箱与当前连接账户一致（脚本用 `status` 实时校验），否则拒绝执行。

```bash
python outlook_setup.py   # 先用测试账户完成认证
bash tests/integration/drill.sh confirm <测试账户邮箱>
```

通过标准 106/106。新增行为时同步更新断言，中英文两份都要。

## 关键设计决策

下面这些决策分散在代码里，不标注很难看出来，改之前务必先读。每条都是踩过坑或反复权衡过的结论，别随手改。

### 请求层

1. **所有请求带不可变 ID 头**。Prefer: IdType="ImmutableId"，事件跨容器移动时 ID 不变，删除/更新才稳定
2. **POST/PATCH 一律不重试**。服务端可能已经处理了请求，重发会造成重复数据；网络异常时提示先 list 确认而不是盲目重发
3. **429 按 Retry-After 等**，没有响应头才走 1/2/4 秒退避；500/503 只有 GET/DELETE 重试
19. **时区头 400 回退走主循环**。个别邮箱不支持 outlook.timezone 头时 Graph 返回 400：剥掉时区头后 continue 回主循环重发（同样经过 429/500/网络异常的重试与错误映射），且只剥一次，剥完仍 400 按普通 API 错误报出

### Graph 语义

4. **全天事件的 Graph 约定**。start 固定 00:00:00，end 是末次次日 00:00 不含，_all_day_range 把它还原成含当天的日期段
5. **查询参数带本地偏移**。isoformat 自带 +08:00 之类的偏移，Graph 才不把时间当 UTC 解析，否则每天 0:00-8:00 的日程会漏
6. **清提醒用 isReminderOn: false**。Graph 忽略 reminderMinutesBeforeStart 的 null PATCH，null 加 isReminderOn 的组合还会报 500
7. **--created-after 走 events 端点**。calendarView 不支持 createdDateTime 过滤
8. **定期系列的例外语义**。对 occurrence 的 PATCH/DELETE 会自动创建例外，只影响这一次；改规则、删整系列必须操作主事件
9. **/instances 不带 $top/$orderby**。该端点对这两个参数有报错先例，且默认按开始时间升序返回；next 在本地截断取最近一次
10. **free 是本地计算**。个人账户的 getSchedule 不可用

### 计算口径

11. **冲突检测窗口**。时段事件前后各扩 1 小时；全天事件查**整个日期段**（多天全天查全程，不只第一天）；calendarView 返回窗口内的全部出现，所以定期系列落在窗口内的每次出现都按实际时间检查
12. **showAs=free 不算占用**。冲突检测和空闲计算都遵循这条；**已取消的定期单次（isCancelled）也不算占用**——calendarView 会返回它们，跳过才不产生假冲突/假忙碌

### 时区与加载

13. **时区探测链**（_detect_local_tz，按顺序取第一个成功）：TZ 环境变量 → Windows 注册表 → 系统 tzinfo 的 key → /etc/timezone → /etc/localtime 符号链接 → /etc/localtime 内容比对 tzdata → 按当前偏移推导 Etc/GMT±N（警告一次）→ UTC（警告）。兜底绝不再把 naive 本地时间静默标成 UTC——那会让新建日程整体偏移。TZ 若是解析不了的 POSIX 规则串（CST-8 等），返回哨兵并**直接走偏移兜底**：TZ 一旦设置就是权威配置，不能回读 /etc 下的另一套时区
13b. **全量 CLDR windowsZones 映射**。官方 Windows 时区名有 140 个左右，映射表必须是全量而不是精选：缺一条就有一个地区的事件被静默按 UTC 显示（差几小时）。已废弃的 XP 时代旧名放 LEGACY_WINDOWS_TZ_MAP，只做解析方向、不参与反查
13c. **_normalize_dt 截断 7 位小数时保留时区后缀**（+08:00/Z），否则带偏移的时间戳会被当成 naive 重新解释，时间直接偏移
14. **LOCAL_TZ 在模块加载时算好**。ocal_time 导入时探测本机时区，之后全局复用，不再探测
15. **导入顺序约束**。ensure_deps() 必须在 ocal_events 导入之前，依赖缺失时顶层导入会先崩，所以 outlook_cal 把导入放在 main() 里

### 命令约定

16. **cmd_* 返回语义**。0 成功，1 失败或用户取消
17. **today/tomorrow/week 复用 cmd_list**。用 setattr 就地改造 args 再调用，不复制逻辑
18. **全天提醒的 N 是"天数"**，时段提醒的 N 是"分钟"，上限 1826 天，即 2629800 分钟；update 里按**转换后的类型**判断——`--no-all-day --remind N` 时 N 必须按分钟算
20. **多天全天**。add/update 给结束日期即多天全天（含当天，Graph 的 end 存末日次日 00:00）；全天分支给的结束带时间则报错，绝不静默截成一天
21. **emoji 输出在窄编码管道下降级不崩**。Windows GBK 管道打印 emoji 会 UnicodeEncodeError，main() 里 harden_stdio() 把 errors 改成 replace（UTF-8 终端不受影响，--json 输出不涉及）
22. **全天日程按邮箱首选时区写入**。机器时区 ≠ 邮箱时区时，全天事件按本机时区写会在 Outlook 里跨两天；setup 授权了 MailboxSettings.Read，每次进程取一次 /me/mailboxSettings 的 timeZone。**旧 token 没这个权限时静默回退本机时区**（与旧版行为一致），但建议用户重跑 setup；status 在两者不同时显示提示行
23. **token 续期有跨进程锁**。续期前加锁（fcntl/msvcrt，非阻塞拿不到就跳过）+ 双检重读 token 文件——两个终端同时续期不会重复请求、不会交叉写坏文件；拿不到锁时两个 refresh token 都有效，最后写者胜，正确性不受影响
24. **删除后提示可恢复**。Graph 的删除进 Outlook「已删除项目」，一段时间内可找回；delete 成功文案后跟一行提示，用户误删不慌
25. **DST 不存在的本地时间有警告**。_local_time_exists 用 aware→UTC→本地 roundtrip 判定（回不到原值 = 被跳变跳过）；add/update/move 写入时段时检查并 stderr 警告，不阻断（歧义时间不告警，fold=0 自洽）
26. **--remind 必须同时打开 isReminderOn**。只 PATCH 分钟数不会自动打开提醒开关（事件此前 --no-remind 时用户设了提醒永远不会响）
27. **协议测试双保险**。test_protocol.py 用 agent 实际使用的提取正则钉住 🆔 缩进/stdout 纯净性；protocol-eval.md 是给人/agent 的端到端评估集（11 条用例）。改输出格式必须两处同步
28. **相对时间由命令在运行时刻解析**。今天/明天/后天/本周X/下周X（中英文，可带 24 小时制或中文时刻"今天下午2点"）直接作时间参数，_parse_dt_arg 按系统时钟换算（now 可注入供测试）——换算不依赖 agent 上下文，"今天"写错成昨天这类事故从根上杜绝。status 输出当前日期（--json 有 today 键），agent 拿不准时用它核对

## 参考资料：Graph API 官方文档

| 主题                         | 链接                                                                                                                                                                                     |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| API 概览                     | https://learn.microsoft.com/en-us/graph/api/overview?view=graph-rest-1.0                                                                                                                 |
| event 资源                   | https://learn.microsoft.com/en-us/graph/api/resources/event?view=graph-rest-1.0                                                                                                          |
| 创建事件                     | https://learn.microsoft.com/en-us/graph/api/user-post-events?view=graph-rest-1.0                                                                                                         |
| calendarView                 | https://learn.microsoft.com/en-us/graph/api/calendar-list-calendarview?view=graph-rest-1.0                                                                                               |
| 定期规则 pattern / range     | https://learn.microsoft.com/en-us/graph/api/resources/recurrencepattern?view=graph-rest-1.0<br>https://learn.microsoft.com/en-us/graph/api/resources/recurrencerange?view=graph-rest-1.0 |
| 实例列表                     | https://learn.microsoft.com/en-us/graph/api/event-list-instances?view=graph-rest-1.0                                                                                                     |
| 查询参数：分页/filter/select | https://learn.microsoft.com/en-us/graph/query-parameters                                                                                                                                 |
| 错误处理                     | https://learn.microsoft.com/en-us/graph/errors                                                                                                                                           |
| 限流                         | https://learn.microsoft.com/en-us/graph/throttling                                                                                                                                       |
| 时区 dateTimeTimeZone        | https://learn.microsoft.com/en-us/graph/api/resources/datetimetimezone?view=graph-rest-1.0                                                                                               |
| 设备码流程 MSAL              | https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-device-code                                                                                                          |
