# 开发者指南

用于维护日历 CLI、skill 指令和测试。用户安装与使用入口见 [README](README.zh-CN.md)，本页说明如何验证修改及定位实现。

## 一次请求如何完成

例如，用户在周一要求“本周五 15:00 开半小时会”：助手用 `context` 确定时区和本周一日期，按四天偏移计算周五，再向 `add` 传入明确起止。CLI 校验时间、构造事件并调用 Graph，返回事件 JSON；助手读取结果核对日期、时段和其他要求。事件存入 Outlook，查询与操作结果输出到终端。

## 验证

在项目根目录安装依赖并运行：

```bash
python -m pip install pytest requests msal tzdata
python -m pytest tests/ -q
python -m compileall -q scripts
```

离线测试模拟网络和认证，覆盖严格日期、显式时区传播与恢复、DST 拒绝、重复结构、查询边界、日程操作、重试、Unicode JSON 和双语 key 完整性。CI 在 Linux、Windows、macOS 上使用 Python 3.10 和 3.13。

模型级评估独立于单测：[触发评估](tests/trigger-eval.zh-CN.md)检查启用范围，[协议评估](tests/protocol-eval.zh-CN.md)检查信息提取，[skill 评估](tests/skill-eval.zh-CN.md)在全新会话的模拟日历中检查完整用户结果。按各评估文档记录实际结果。

需要验证真实账户时，按[实机集成测试](tests/integration/README.zh-CN.md)单独运行；该流程会创建和清理真实日程。

测试摘要显示在终端。需要机器可读报告时，使用 `python -m pytest tests/ -q --junitxml=test-results.xml`，结果保存在项目根目录的 `test-results.xml`；该报告由执行者按需生成。

## 职责边界

模型负责理解自然语言日期、重复要求、日程对象、缺失信息及单次/系列范围，传入明确参数并核实结果。Python 提供确定的日期运算，校验具体参数，处理日历和时区语义，并调用 Graph。

- `context --json` 无需日历认证即可返回有效时钟和时区名称。`date --base YYYY-MM-DD --days N --json` 按有符号天数计算日期，不读取时钟。
- `_parse_dt_arg` 只接受补零的 `YYYY-MM-DD`、`YYYY-MM-DD HH:MM`、`YYYY-MM-DDTHH:MM`。仅日期参数拒绝时刻；秒、时区后缀、多余空白和语言表达式均非法。Graph 响应另走更宽容的解析路径。
- `list` 必须给 `--from` 或 `--created-after`，`free` 必须给日期。日历窗口从本地零点开始，以最后一日的次日零点为不包含的结束边界。`--created-before` 是创建时间的不包含上界。
- 创建时段日程必须给开始和结束；创建全天日程必须加 `--all-day`，可选的包含式结束日期默认等于开始日期。类型转换必须给新类型的两个边界。部分更新保留未提供字段，并校验最终范围。
- 重复输入是 Graph pattern JSON 对象，可直接传入或读取 UTF-8 文件。适用字段必须明确提供；不支持、重复、缺失或与类型无关的字段均被拒绝。六种规则及结束条件见[定期日程](references/recurring-events.zh-CN.md)。
- 写入前固定日期、时刻、时区、目标及字段；验证或恢复过程中复用这些值，跨过午夜也不重新解释原相对表述。

## 代码结构

| 文件 | 职责 |
|---|---|
| `scripts/outlook_cal.py` | 参数解析、语言预扫、规则文件读取、命令分派、单次时区覆盖、结构化错误 |
| `scripts/ocal_context.py` | 离线时钟上下文和自然日运算 |
| `scripts/ocal_time.py` | 默认时区探测、严格日期输入、Graph 时间转换、全天日期范围 |
| `scripts/ocal_recurrence.py` | 结构化规则校验、range 构造、人类描述、保守的出现序号计算 |
| `scripts/ocal_events.py` | 日历命令、目标定位、冲突/空闲计算、结果显示 |
| `scripts/ocal_graph.py` | Graph 请求、请求头、重试/错误映射、分页 |
| `scripts/ocal_auth.py` | 凭据获取/续期与跨进程锁 |
| `scripts/outlook_setup.py` | 设备码登录；导入模块不会开始认证 |
| `scripts/ocal_bootstrap.py` | 依赖自检与安装；仅依赖标准库和 i18n |
| `scripts/ocal_i18n.py`、`scripts/ocal_errors.py` | 双语文案与面向用户的 `CalError` |

发布时保留完整 `scripts/` 目录，要求 Python 3.10+。Bootstrap 必须先安装缺失的 `requests`、`msal`、`tzdata`，再导入日历模块；反过来会使首次运行在自动安装前就因缺少依赖而失败。

## 日期与时区语义

1. `ocal_time` 加载时探测默认时区：`TZ` → Windows 注册表 → 系统时区 key → `/etc/timezone` → `/etc/localtime` 链接/内容 → 固定偏移回退 → UTC 回退。偏移和 UTC 回退会警告。已显式设置但无法解析的 POSIX `TZ` 使用偏移回退，不读取另一份无关系统配置。
2. `--timezone` 校验 IANA 或当前 Windows 名称，并一致应用于上下文、输入解释、API 偏好、重复规则和显示。自动探测和显式传入的 IANA 名称均保留自身地区规则，不替换成覆盖更广的 Windows 别名。分派结束后恢复模块原值，避免同进程多次调用泄漏时区修改。
3. Windows 名称使用 CLDR 映射；旧名称别名仍用于读取 Graph 响应。保持 `tzdata` 可用，Windows 系统往往不自带 IANA 数据库。
4. 时段写入拒绝夏令时跳变中不存在或出现两次的墙钟时间。`_local_time_exists` 通过 aware → UTC → local 往返检测缺失时间，fold 偏移差异检测歧义。先明确实际时刻；本地时间重复时可改用明确的 UTC 输入。
   空闲查询还会拒绝起止不存在/有歧义或窗口内 UTC 偏移发生变化的区间，因为纯 `HH:MM` 时段无法表示重复墙钟时间的两次出现。明确实际 UTC 窗口后用 `--timezone UTC` 查询；不跨越跳变的普通窗口仍可使用。
5. 全天写入优先使用邮箱时区，取不到则用有效时区。CLI 结束日期包含当天，Graph 则保存次日零点作为不包含的结束。读取全天范围时不将日期经 UTC 换算。重复范围也使用最终日程的时区。
6. 查询边界分别携带自己的偏移，包括跨夏令时的情况。Graph 时间可能含七位小数；截断精度时必须保留 `Z` 或数字时区后缀。

## Graph 请求与恢复

- 事件请求使用 `Prefer: IdType="ImmutableId"`，不可从标题或时间拼造 ID；写入 URL 路径的 ID 均需转义。
- POST/PATCH 的网络错误可能发生在服务端已处理之后，不能盲目重试，应先查询服务端状态。GET/DELETE 可重试暂时性网络错误和 500/503；429 遵循 `Retry-After`，缺少该头时采用有上限的指数退避。
- 时区相关的 400 可以移除 `outlook.timezone` 重试一次，仍走统一的重试/错误处理循环；第二次拒绝正常报错。
- 按发生日期查询使用 `calendarView` 展开单次出现；创建筛选用支持 `createdDateTime` 的 `/me/events`，这些结果会包含该字段。分页跟随 `@odata.nextLink`，防御性上限为 200 页。
- `/instances` 查询不带 `$top`、`$orderby`；`next` 在查询窗口内取最近出现。本地出现序号仅用于显示，只计算可可靠判断的 daily 和 interval 为 1 的 weekly；复杂规则或无法可靠判断的日期省略序号。
- 修改/删除某次只作用于该次；修改系列规则须操作主事件，可能重置例外。规则更新会重建完整 range：两个结束选项均省略表示无截止，因此模型要保留原截止日期或次数时必须明确传入。
- 冲突检查覆盖全天日程的完整日期范围及时段日程前后扩展窗口。`showAs=free` 和已取消事件不占用时间。个人账户不支持 `getSchedule`，因此 `free` 从事件在本地计算空闲段。
- 关闭提醒写 `isReminderOn: false`，不能依赖分钟数置空。设置 `--remind` 同时打开 `isReminderOn`；单位取决于最终类型：时段按分钟，全天按天，全天上限 1826 天。
- 邮箱时区读取需要 `MailboxSettings.Read`，权限不可用时回退有效时区。登录还申请 `Calendars.ReadWrite`；`status` 通过 `/me/calendar` 识别账户。
- 凭据续期使用跨进程锁并重新检查存储内容，减少并发刷新和写入竞争。导入认证模块不能触发设备码交互。

## 输出与国际化

模型优先使用 JSON。`--json` 下每次操作向 stdout 输出一个 JSON 值，诊断走 stderr。错误保留 `error`、`exit: 1` 且退出码非零；Graph/网络错误可附加稳定的 `code`、`http_status` 和 `outcome_unknown`，完整字段见[命令参考](references/commands.zh-CN.md)。写入超时、服务端错误及无法解析的成功响应标记结果不明；未连接的 `status` 保留连接状态对象。`--help` 是文本。JSON 采用 ASCII 转义，使 Unicode 经过 Windows GBK 管道后仍能被解码完整还原。

人类输出仍由结构测试覆盖：结果 🆔 行在列表中缩进四格、add 中三格、read 中顶格；read 用 🆕 加冒号表示系列主 ID。空闲段格式为 `HH:MM-HH:MM`；没有列出时段本身无法区分全忙和全空闲，应使用 JSON。冲突警告可能包含已有事件 ID，应放在 stderr。文本模式的交互确认仍在 stdout。

面向用户的文案通过 `ocal_i18n.t()`。语言优先级为 `--lang` → `OCAL_LANG` → 系统探测。两种语言表都要填全；锚点和 JSON key 与语言无关，译文不是解析契约。窄编码文本管道会替换不支持的 emoji，这种情况下不要依赖 emoji 提取。

文档按英文默认文件名与中文 `.zh-CN` 成对维护；两个 SKILL 文件保留相同的英文 frontmatter description 和版本。版本采用 x.y.z：不兼容契约升主版本，新行为升次版本，维护升补丁版本。行为改变时同步示例和断言。

## API 参考

- [Event 资源](https://learn.microsoft.com/en-us/graph/api/resources/event?view=graph-rest-1.0)
- [Calendar view](https://learn.microsoft.com/en-us/graph/api/calendar-list-calendarview?view=graph-rest-1.0)
- [重复 pattern](https://learn.microsoft.com/en-us/graph/api/resources/recurrencepattern?view=graph-rest-1.0) 与 [range](https://learn.microsoft.com/en-us/graph/api/resources/recurrencerange?view=graph-rest-1.0)
- [单次出现列表](https://learn.microsoft.com/en-us/graph/api/event-list-instances?view=graph-rest-1.0)
- [时区值](https://learn.microsoft.com/en-us/graph/api/resources/datetimetimezone?view=graph-rest-1.0)
- [错误处理](https://learn.microsoft.com/en-us/graph/errors)与[限流](https://learn.microsoft.com/en-us/graph/throttling)
