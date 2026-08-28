# 开发者说明

面向 skill 维护者的文档：代码结构、协议、设计决策、测试方法。
本说明的目标是让开发者无需阅读（或仅需少量阅读）代码即可理解系统的运转方式，
也使下一代开发者可以直接基于本文档进行开发，无需逆向工程。

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
  test_protocol.py      # 输出协议解析：agent 提取正则逐条固化（🆔 缩进/时段格式/stdout 纯净性）
  trigger-eval.md       # 触发评估集：改 description 时对照验证触发/不触发
  protocol-eval.md      # 输出协议评估集：新会话里端到端验证提取规则，11/11
  integration/          # 可选：真实账户实机演练，需专用测试账户，见其 README
    drill.sh            # 106 项行为断言，中文输出
    drill-en.sh         # 同上，英文输出
    README.md           # 用法与警告

.github/workflows/
  tests.yml             # CI：三平台（Linux/Windows/macOS）× Python 3.10/3.13 跑离线测试

references/             # 用户文档
  commands.md           # 命令完整参考（英文版 commands_EN.md）
  recurring-events.md   # 定期日程专题（英文版 recurring-events_EN.md）
  configuration.md      # 连接配置（英文版 configuration_EN.md）
  troubleshooting.md    # 故障排除（英文版 troubleshooting_EN.md）
  azure-app-setup.md    # 自带 Azure 应用注册（英文版 azure-app-setup_EN.md）
```

## 运行前提

- `scripts/` 目录整体分发，入口和全部 `ocal_*.py` 必须放在一起
- 依赖 requests、msal、tzdata，通常无需手动安装，首次运行会自动 pip 安装，见依赖自检
- 首次使用前先执行 `python outlook_setup.py` 完成设备码认证

## 版本号规则

`version` 为 x.y.z 三段，各段的递增时机：

| 段  | 递增时机                                                 |
| --- | -------------------------------------------------------- |
| x   | 破坏性变更：命令不兼容、配置格式变化、行为协议改变       |
| y   | 新功能或行为变化：新增命令/参数、输出文案变化、依赖变化  |
| z   | 纯维护：bug 修复、注释重构，行为不变                     |

## 改动约定

- 修改输出前应先阅读输出协议章节，评估是否可能破坏下游解析。zh/en 文案已被测试逐字固化，任何改动须同步更新两种语言的断言并递增 y 版本号，不应随意修改；诸如「每周周五」这类既有显示习惯应保持原样，不予修正
- 重构后须运行回归测试（见测试章节）：离线单元测试全部通过，且（若涉及协议变更）实机演练 106/106 通过，方视为合格
- 新增行为时须同步更新 `tests/` 中的断言，中英文两个语言版本均需更新；输出格式变更必须同步更新 `tests/protocol-eval.md` 与 `test_protocol.py`

## 依赖自检

- `ensure_deps()` 必须在导入 `ocal_events` 之前调用，导入顺序约束的完整解释见关键设计决策
- `tzdata` 是 Windows 时区解析正确的关键依赖：缺失时将静默回退至 UTC，导致时间偏差数小时，详见关键设计决策的时区小节
- bootstrap 自身仅允许使用 stdlib 与 ocal_i18n，提示文案统一经 t() 的 deps_* 键输出

## 多语言约定

- print / CalError / input 提示等所有用户可见文案均经 `ocal_i18n.t()` 输出，禁止硬编码中文
- 语言优先级：`--lang` 参数 > `OCAL_LANG` 环境变量 > 系统语言检测（中文系统用 zh，其余用 en）
- emoji 锚点 🆔/✅/⚠️/🆕 等属于输出协议的一部分：🆔 行即事件 ID，脚本与 agent 均从中提取，两种语言共用，绝不翻译；`--json` 输出与语言无关
- **自然语言文案不属于协议**：协议只承诺锚点、缩进、冒号/括号结构与时段/JSON 格式；行内文案（如「系列主事件ID」「确认?」「无空闲时段」）随语言翻译，agent 不应依赖具体文案
- 日期/星期使用 `d_md`/`date_weekday`/`weekday` 等运行时函数。语言在模块导入后才确定，不能定义为常量
- 新增文案必须同时填充 zh/en 两张表；键缺失时依次回退至中文、再回退至键名，便于在开发期快速识别遗漏的翻译

## 输出协议：字符串协议

命令的人类可读输出构成一套稳定协议，agent 与脚本均依赖其解析结果。协议的意义在于：面对任意一段输出，无需阅读代码即可明确每行的含义及事件 ID 所在位置。修改输出前应先对照本节，评估是否可能破坏下游解析。

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

1. 🆔 行是事件 ID 的唯一来源，agent 应从中提取，严禁猜测或编造
2. 锚点与**结构**（缩进/冒号/括号/时段格式）是语言无关的硬协议，zh/en 完全一致，绝不翻译；**行内自然语言文案不是协议**——如「系列主事件ID / Series master event ID」「确认? / Confirm?」由 i18n 表随语言翻译，agent 提取信息只依赖锚点与结构，不依赖具体文案
3. 🆔 行缩进必须稳定：list 中为 4 空格，add 中为 3 空格，read 中顶格。drill 脚本用 sed 按缩进抓取 ID，改动缩进即破坏回归测试
4. 错误统一以 ❌ 前缀加友好文案输出，退出码为 1；--json 模式下输出 {"error": ..., "exit": 1}
5. 确认提示结构固定为 `{文案}? [y/N]`，接受 y/yes（文案随语言：zh `确认?`、en `Confirm?`）；delete 的系列选择为 [1]/[2] 两档，接受 2/s/series 及本地化词（zh: `系列`）
6. --json 模式 stdout 仅输出 JSON，人类提示全部走 stderr；非 --json 模式下，**非交互路径的提示/警告**（冲突警告、全天自动提示、解除/重置定期警告、无字段更新提示）也一律走 stderr——stdout 只保留结果、🆔 协议行与交互确认对话。冲突警告中包含现有日程的 🆔，若进入 stdout，agent 将无法区分哪个 🆔 属于新日程

### 行结构

- list 每条占两行：`    {图标} {时间}  {标题}{定期标记}{类别}`，下一行为 `    🆔 {ID}`
- 定期标记为 🔁 加括号后缀（文案随语言，如 zh `(系列)`/`(已修改)`/`(已取消)`、en `(series)` 等），系列主事件行尾还带有规则描述
- read 的 ID 行为 `🆔 {ID}`；系列上下文为 `🆕 {文案}: {ID}`——锚点+冒号结构是协议，冒号前文案随语言（zh `系列主事件ID`、en `Series master event ID`）
- free 每行为 `📅 {日期} {星期}：{内容}`；有 HH:MM-HH:MM 段 = 部分空闲，无时段列表 = 整天空闲或无空闲（区分依赖文案或 `--json`）

### 时间与日期

- 时间固定为 MM/DD HH:MM，数字格式在两种语言下一致
- 日期 08月10日 / 08/10，星期 周一 / Mon，全天 / All day，日期范围 ~ / -
- 定期描述：每天 / 每N天 / 每周X / 每N周X / 每月N日 / 每月第N个周X / 每年X月X日，结束条件后缀（共N次）/（至日期）

## 测试

### 单元测试：日常开发主入口

离线运行，网络请求全部 mock，CI 可用：

```bash
python -m pytest tests/          # 需要 pytest
python -m py_compile scripts/*.py
```

覆盖范围：时间解析边界、定期规则的全部写法与非法输入、i18n 字符串表完整性（脚本中每个 t() 调用键必须同时存在于 zh/en 两张表中）、冲突/空闲计算、Graph 重试与错误映射、token 续期与跨进程锁、邮箱时区回退、DST 跳变检测、输出协议解析（test_protocol.py），以及网络层被 mock 的各命令路径。

CI：`.github/workflows/tests.yml` 在 Linux/Windows/macOS × Python 3.10/3.13 上运行同一套离线测试——时区探测链、跨平台路径与编码降级均依赖 CI 提供兜底保障。

注意：`outlook_setup.py` 的 main() 设有守卫——**导入该模块不会触发设备码流程**，仅当直接运行 `python outlook_setup.py`（即以 `__main__` 方式执行）时才进入流程。进入后终端显示"打开 microsoft.com/link 并输入代码"，随即开始轮询等待授权：界面看似停滞，实际是在等待用户在浏览器中完成授权，超时后自动退出。在单元测试或 REPL 中导入该模块仅加载模块，不会阻塞或弹出验证码。

### 触发评估：改 description 用

description 决定 skill 何时被触发，修改前应先运行一遍 `tests/trigger-eval.md`：
12 条应触发的请求与 6 条不应触发的请求，需在全新会话中逐条验证。
对于漏触发，补充关键词；对于误触发，增加排除条件。合格标准为 12/12 与 6/6。

### 协议评估：改输出格式用

输出格式是 agent/脚本解析所依赖的契约，修改前应先运行一遍 `tests/protocol-eval.md`：
11 条"从输出中提取 🆔/时段/错误"的端到端用例，需在全新会话中逐条验证；
同一套正则已被 `test_protocol.py` 自动化固化。合格标准为 11/11。

### 实机集成演练：可选

单元测试无法验证真实 Graph 的行为，`tests/integration/` 中提供两份 106 项断言脚本作为补充验证。**必须使用专用测试账户**：脚本开头的基线清理会删除 ±400 天窗口内的全部日程，严禁指向个人真实日历。用法参见 `tests/integration/README.md`。

> ⚠️ **agent 必读**：运行 drill.sh / drill-en.sh 之前，必须向用户明确警示：脚本会**永久删除 ±400 天窗口内的全部日程及全部定期系列主事件**（不可恢复），且必须获得用户明确同意后方可执行；仅允许对专用测试账户运行。脚本设有双重防呆校验：必须传入 `confirm` 参数，且指定的测试账户邮箱必须与当前连接账户一致（脚本通过 `status` 实时校验），否则拒绝执行。

```bash
python outlook_setup.py   # 先用测试账户完成认证
bash tests/integration/drill.sh confirm <测试账户邮箱>
```

通过标准为 106/106。新增行为时须同步更新断言，中英文两份均需更新。

## 关键设计决策

以下决策分散于代码各处，未经标注难以察觉，修改前务必通读。每一条均源自实际故障经验或反复权衡，不应随意改动。

### 请求层

1. **所有请求携带不可变 ID 头**。Prefer: IdType="ImmutableId"，事件跨容器移动时 ID 保持不变，删除/更新操作方可稳定
2. **POST/PATCH 一律不重试**。触发场景：网络抖动或超时——请求可能已到达 Graph 并成功创建日程，仅响应在回程途中丢失；此时盲目重发将在日历中生成两条重复日程。因此 POST/PATCH 在遭遇网络异常时**不进行重试**，而是提示用户先执行 `list` 确认日程是否已创建，再决定是否重发
3. **429 按 Retry-After 等待**。仅在缺少该响应头时采用 1/2/4 秒退避；500/503 仅对 GET/DELETE 重试
4. **时区头 400 回退走主循环**。个别邮箱不支持 outlook.timezone 头时，Graph 返回 400：剥掉时区头后 continue 回主循环重发（同样经过 429/500/网络异常的重试与错误映射），且仅剥一次，剥完仍 400 则按普通 API 错误报出

### Graph 语义

5. **全天事件的 Graph 约定**。start 固定为 00:00:00，end 为末日的次日 00:00（不含），_all_day_range 将其还原为含末日的日期区间
6. **查询参数携带本地偏移**。isoformat 输出自带 +08:00 等偏移，Graph 方不会将时间误作 UTC 解析；否则每日 0:00-8:00 的日程将被遗漏
7. **清提醒用 isReminderOn: false**。触发场景：用户执行 `update ... --no-remind` 时，程序 PATCH `{reminderMinutesBeforeStart: null}`——Graph 会**静默忽略**该字段，提醒实际未被清除，届时仍会照常触发；若改用 `{reminderMinutesBeforeStart: null, isReminderOn: true}` 组合，Graph 将直接返回 500，命令失败。因此清除提醒必须 PATCH `{isReminderOn: false}`（并同时置空分钟数）
8. **--created-after 走 events 端点**。calendarView 不支持 createdDateTime 过滤
9. **定期系列的例外语义**。对 occurrence 的 PATCH/DELETE 会自动创建例外，仅影响该次出现；修改规则、删除整系列则必须操作主事件
10. **/instances 不携带 $top/$orderby**。该端点对上述两个参数存在报错先例，且默认按开始时间升序返回；`next` 在本地截断，取最近的一次
11. **free 是本地计算**。个人账户的 getSchedule 不可用

### 计算口径

12. **冲突检测窗口**。时段事件在前后各扩展 1 小时；全天事件检查**完整日期区间**（多天全天检查全程，而非仅首日）；calendarView 返回窗口内的全部出现，因此定期系列落在窗口内的每次出现均按实际时间检查
13. **showAs=free 不算占用**。冲突检测与空闲计算均遵循此规则；**已取消的定期单次（isCancelled）同样不视为占用**——calendarView 会返回这些出现，须将其跳过，方能避免误报冲突/忙碌

### 时区与加载

14. **时区探测链**（_detect_local_tz，按顺序取第一个成功）：TZ 环境变量 → Windows 注册表 → 系统 tzinfo 的 key → /etc/timezone → /etc/localtime 符号链接 → /etc/localtime 内容比对 tzdata → 按当前偏移推导 Etc/GMT±N（警告一次）→ UTC（警告）。兜底逻辑绝不再将 naive 本地时间静默标记为 UTC——否则新建日程将整体偏移。若 TZ 为无法解析的 POSIX 规则串（如 CST-8），则返回哨兵并**直接采用偏移兜底**：TZ 一经设置即为权威配置，不得回读 /etc 下的另一套时区
14b. **全量 CLDR windowsZones 映射**。官方 Windows 时区名约有 140 个，映射表必须为全量而非精选：任一缺失都将导致对应地区的事件被静默按 UTC 显示（偏差数小时）。已废弃的 XP 时代旧名放于 LEGACY_WINDOWS_TZ_MAP，仅用于解析方向，不参与反查
14c. **_normalize_dt 截断 7 位小数时保留时区后缀**（+08:00/Z）。触发场景：Graph 返回的 ISO 时间戳可能带有 7 位小数（如 `2026-08-10T09:00:00.1234567+08:00`），而 Python 的 `datetime.fromisoformat` 仅接受 6 位，因此必须截断。截断时若将 `+08:00`/`Z` 后缀一并去除，datetime 将变为 naive（无时区），后续格式化或写回 Graph 时会被当作"无时区时间"重新解释——东八区的日程将整体偏移 8 小时。故截断小数时必须保留时区后缀
15. **LOCAL_TZ 在模块加载时算好**。ocal_time 在导入时探测本机时区，此后全局复用，不再重复探测
16. **导入顺序约束**。ensure_deps() 必须在 ocal_events 导入之前。触发场景：用户机器未安装 requests/msal/tzdata 时的首次运行——若 `outlook_cal.py` 在模块顶层执行 `import ocal_events`，Python 在模块加载的瞬间即抛出 `ModuleNotFoundError: No module named 'requests'`（或 msal/tzdata），**崩溃发生在 ensure_deps() 执行之前**：用户仅能看到完整的 Python 堆栈，而看不到"正在自动安装依赖"的引导提示，首次运行自动安装依赖的机制就此失效，用户将误判工具不可用。因此 outlook_cal 将全部导入置于 main() 内：先执行 ensure_deps() 完成依赖安装，再进行导入

### 命令约定

17. **cmd_* 返回语义**。0 成功，1 失败或用户取消
18. **today/tomorrow/week 复用 cmd_list**。通过 setattr 就地修改 args 后调用 cmd_list，避免逻辑重复
19. **全天提醒的 N 是"天数"**，时段提醒的 N 是"分钟"，上限 1826 天，即 2629800 分钟；update 中按**转换后的类型**判断——`--no-all-day --remind N` 时 N 必须按分钟计
20. **多天全天**。add/update 给定结束日期即多天全天（含末日，Graph 的 end 存末日的次日 00:00）；全天分支中结束时间若带有时间部分则报错，严禁静默截断为单日
21. **emoji 输出在窄编码管道下降级不崩**。触发场景：中文 Windows 的控制台代码页为 GBK（cp936）。一旦输出被重定向或经管道传输（如 `python outlook_cal.py list > out.txt`、`... | findstr 周会`），stdout 编码将变为 GBK，此时 `print("📅 08月10日")` 抛出 `UnicodeEncodeError: 'gbk' codec can't encode character '\U0001f4c5'`——程序崩溃、退出码为 1、结果全部丢失。main() 中的 harden_stdio() 将 stdout/stderr 的 errors 改为 replace：emoji 降级为 `?` 占位符，日期、标题、🆔 ID 等文字照常输出（ID 为 ASCII，agent 解析不受影响）。UTF-8 终端可正常编码 emoji，不会触发该问题；--json 输出为纯 ASCII，不涉及此场景
22. **全天日程按邮箱首选时区写入**。机器时区 ≠ 邮箱时区时，全天事件按本机时区写入会在 Outlook 中跨两天显示；setup 授权 Calendars.ReadWrite + MailboxSettings.Read（登录另需 User.Read 基础权限），每个进程取一次 /me/mailboxSettings 的 timeZone。**旧 token 缺少该权限时静默回退至本机时区**（与旧版行为一致），但建议用户重跑 setup；当两者不同时，status 会显示提示行
23. **token 续期有跨进程锁**。触发场景：token 过期后，两个终端（或终端与定时任务）同时执行命令，两个进程均会刷新 token 并写入 `~/.outlook_cal_token.json`。若不加锁，写入将相互交错：一个进程刚截断文件或写入一半时，另一进程同时写入，文件内容交错损坏——此后任何命令的 `json.load` 都会抛出 `JSONDecodeError`，全部命令立即失败，用户只能删除 token 文件并重新登录。处理方式：续期前先加锁（fcntl/msvcrt，非阻塞，获取失败则跳过），并双重检查后重读 token 文件——两个终端同时续期不会产生重复请求，也不会写坏文件；无法获取锁说明另一进程正在续期，应跳过续期，直接重读其刚写入的 token。极端情况下两个 refresh token 均有效，最后写入者生效，正确性不受影响
24. **删除后提示可恢复**。Graph 的删除操作会将日程移入 Outlook「已删除项目」，在一定期限内可恢复；delete 成功文案后会附加一行提示，以缓解用户误删时的顾虑
25. **DST 不存在的本地时间有警告**。_local_time_exists 通过 aware→UTC→本地 roundtrip 判定（无法回到原值即被跳变跳过）；add/update/move 写入时段时进行检查，并通过 stderr 发出警告，不阻断操作（歧义时间不告警，fold=0 时自洽）
26. **--remind 必须同时打开 isReminderOn**。仅 PATCH 分钟数不会自动开启提醒开关（若事件此前曾执行 --no-remind，用户设置提醒后将永远无法触发）
27. **协议测试双保险**。test_protocol.py 使用 agent 实际采用的提取正则固化 🆔 缩进/stdout 纯净性；protocol-eval.md 是面向人/agent 的端到端评估集（11 条用例）。修改输出格式必须两处同步。**协议只到结构层**：正则只钉锚点/缩进/时段/JSON 结构，不钉自然语言文案；文案逐字稳定由 i18n 表测试（test_i18n.py）保证，两套测试互不越界
28. **相对时间由命令在运行时刻解析**。今天/明天/后天/本周X/下周X（中英文，可附带 24 小时制时刻或中文时刻如"今天下午2点"）可直接作为时间参数，_parse_dt_arg 按系统时钟换算（now 可注入，便于测试）——换算不依赖 agent 上下文，从根本上杜绝"今天"被误判为"昨天"之类的事故。status 输出当前日期（--json 模式提供 today 键）。**SKILL 操作铁律第 1 条与本条配套：每次操作前须先通过命令行获取当前时间与时区**（Windows 使用 `Get-Date`/`Get-TimeZone`，Linux/macOS 使用 `date`），agent 一律以本次获取的结果为准，不得沿用旧会话中的日期/时区记忆
29. **写命令支持 --search 定位（找+改合并）**。update/move/delete 的 event_id 改为可缺省，配合 `--search "词"` 在「过去 7 天 ~ 未来 30 天」窗口内搜索定位：唯一匹配直接操作，多匹配报错并列出候选（标题+时间+🆔，供 agent 二次指定），零匹配报错提示换词或扩窗——把"找+改"从多次调用压成一次，减少 agent 往返。定位本身无副作用，read/next 保持 ID 必填不做合并

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
