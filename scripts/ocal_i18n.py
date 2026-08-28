"""ocal_i18n — 多语言支持：语言解析、字符串表、语言相关日期/星期格式化。

语言优先级：--lang 参数 > OCAL_LANG 环境变量 > 系统语言检测 > 默认 zh。
所有用户可见文案（print / CalError / 确认提示 / 定期描述）都必须经 t() 走语言表；
emoji 锚点（🆔/✅/⚠️…）是协议标记，两种语言共用，不翻译。
"""
import os

LANGS = ("zh", "en")
DEFAULT_LANG = "zh"

LANG = DEFAULT_LANG


def _detect_os_lang():
    """按系统语言猜一个默认值：中文系统 → zh，其余 → en（国际化默认）。

    :return: "zh" 或 "en"
    """
    try:
        import ctypes
        code = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        if code & 0xFF == 0x04:  # 主语言 = 中文
            return "zh"
        return "en"
    except Exception:
        pass
    lang = (os.environ.get("LANG") or os.environ.get("LC_ALL") or "").lower()
    if lang.startswith("zh"):
        return "zh"
    if lang.startswith("en"):
        return "en"
    return "en"


def resolve_lang(override=None):
    """按优先级定语言：--lang 参数 > OCAL_LANG 环境变量 > 系统检测。

    传入的值不在支持列表里就忽略，落到下一级。

    :param override: --lang 给的显式值，可空
    :return: "zh" 或 "en"
    """
    for cand in (override, os.environ.get("OCAL_LANG", "")):
        if cand:
            cand = str(cand).strip().lower()
            if cand in LANGS:
                return cand
    return _detect_os_lang()


def set_lang(override=None):
    """设置当前语言。

    :param override: --lang 给的显式值，可空
    :return: 最终生效的语言
    """
    global LANG
    LANG = resolve_lang(override)
    return LANG


def get_lang():
    """当前生效的语言。

    :return: "zh" 或 "en"
    """
    return LANG


# ── 字符串表 ──────────────────────────────────────
# 约定：键即协议。缺键回退中文再回退键名，方便开发期发现漏翻。

T = {
    "zh": {
        # ── 通用 ──
        "all_day": "全天",
        "date_range_sep": "~",
        "list_join": "、",
        "filter_join": " + ",
        "err_auth_first": "请先认证: python outlook_setup.py（无参数即内置应用）",
        "err_id_required": "事件ID不能为空（请先 list 获取 🆔）",
        "err_search_none": "未找到匹配「{s}」的日程（搜索窗口：过去 7 天 ~ 未来 30 天）。可换关键词，或先 list 扩大范围后指定事件 ID",
        "err_search_multi": "「{s}」匹配到多个日程，请指定事件 ID 或缩小关键词：\n{list}",
        "help_search_target": "不传事件 ID 时按关键词搜索定位（唯一匹配直接操作，多匹配报错列出候选）",
        "err_end_after_start": "结束时间必须晚于开始时间",
        "confirm_prompt": "   确认? [y/N] ",
        "cancel": "🚫 已取消",
        "cancel_eof": "\n🚫 已取消（非交互环境，请用 -y 跳过确认）",
        "cancel_eof_delete": "\n🚫 已取消（非交互环境，请用 -y 或 --series 指定）",
        "importance_line": "   ⭐ 重要度: {v}",
        "private_line": "   🔒 私密",
        "showas_line": "   📊 显示为: {v}",
        "read_importance": "⭐ 重要度: {v}",
        "read_private": "🔒 私密",
        "read_showas": "📊 显示为: {v}",
        "date_all_day": "   📅 {d} 全天",
        # ── status ──
        "status_not_connected": "🔒 尚未连接日历",
        "status_run_setup": "   请先运行: python outlook_setup.py（无参数即内置应用）",
        "status_api_error": "⚠️  日历 API 连接异常: {e}",
        "status_connected": "✅ 已连接到 Outlook 日历",
        "status_today": "   📅 当前日期: {d}",
        "status_mailbox_tz": "   🌐 邮箱时区: {tz}（与本机不同；全天日程已按邮箱时区写入）",
        "status_expiry": "   🔑 登录有效期: {h} 小时 {m} 分钟",
        "status_expired_auto": "   🔑 登录已过期，将在下次操作时自动续期",
        # ── list / 显示 ──
        "list_empty": "\n✨ {title}：没有符合条件的日程\n",
        "list_header": "\n📅 {title}:\n",
        "list_count": "  {d}：{n} 条",
        "rec_cancelled": " 🔁(已取消)",
        "rec_modified": " 🔁(已修改)",
        "rec_series": " 🔁(系列)",
        "title_from": "{d} 起 {n} 天的安排",
        "title_range": "过去 {p} 天 ~ 未来 {n} 天的安排",
        "title_next": "接下来 {n} 天的安排",
        "title_created": "{d} 之后添加的日程",
        "suffix_reminders": "（仅带提醒）",
        "filter_contains": "含「{s}」",
        "filter_category": "类别「{c}」",
        "filter_suffix": "（筛选: {c}）",
        "list_no_match": "🔍 共 {n} 条日程，{title}：无匹配\n",
        # ── add ──
        "add_allday_hint": "ℹ️ 未提供具体时间，已按全天处理（如需时段请用 YYYY-MM-DD HH:MM 格式）",
        "err_repeat_until": "重复截止/次数需要配合 --repeat 使用",
        "err_remind_negative": "提醒时间不能为负数",
        "err_allday_remind_max": "全天提醒最多支持 {n} 天（当前 {m} 天）",
        "remind_days": "提前 {n} 天提醒",
        "remind_minutes": "提前 {n} 分钟提醒",
        "conflict_header": "\n⚠️ 与以下现有日程重叠（如需仍添加请忽略）：",
        "add_success": "\n✅ 已添加到日历:",
        # ── update ──
        "err_series_rule": "该日程是定期系列的一次出现，修改系列规则请先 read 获取「🆕 系列主事件ID」，再对主事件修改",
        "warn_repeat_removed": "⚠️ 已解除定期，该日程将变为单次日程",
        "warn_repeat_reset": "⚠️ 修改系列规则会重置该系列已删除/已修改的例外",
        "warn_nothing_to_update": "⚠️ 没有要修改的字段（用 --subject/--start/--end/--all-day/-l/-b/--category/--importance/--private/--busy/--remind/--repeat 指定）",
        "warn_occurrence_only": "⚠️ 该事件是定期系列的一次出现，本次修改只影响这一次（创建例外），不影响整个系列",
        "confirm_update": "📋 将更新「{s}」: {changes}",
        "update_success": "\n✅ 已更新:",
        "ch_subject": "标题",
        "ch_allday_date": "全天日期",
        "ch_time": "时间",
        "ch_location": "地点",
        "ch_body": "备注",
        "ch_category": "类别",
        "ch_importance": "重要度",
        "ch_private": "私密",
        "ch_busy": "忙闲",
        "ch_reminder": "提醒",
        "ch_recurrence": "重复规则",
        # ── read ──
        "read_added": "🕘 添加时间: {t}",
        "read_organizer": "👤 组织者: {a}",
        "read_series": "🔁 所属系列: {s}（{rec}）",
        "read_occ_num": "   这是该系列的第 {n} 次出现；修改/删除仅影响本次",
        "read_master_id": "🆕 系列主事件ID: {id}",
        "read_series_fail": "🔁 所属定期系列（主事件信息读取失败）",
        # ── delete ──
        "warn_occ_of_series": "⚠️ 该事件是定期系列「{s}」的一次出现",
        "delete_choice": "   [1] 仅删除本次出现   [2] 删除整个系列",
        "delete_prompt": "   选择 (默认1): ",
        "warn_series_all": "⚠️ 这是整个定期系列，删除将移除全部出现！",
        "confirm_delete": "📋 将删除「{s}」",
        "deleted_series": "🗑️ 已从日历中移除整个系列「{s}」（含全部出现）",
        "deleted_occurrence": "🗑️ 已从日历中移除本次出现「{s}」（其余出现保留）",
        "deleted_single": "🗑️ 已从日历中移除「{s}」",
        "delete_recoverable": "   💡 刚删的日程在 Outlook「已删除项目」中仍可找回（一段时间内）",
        # ── move ──
        "err_days_to": "--days 与 --to 不能同时使用",
        "err_move_args": "请指定 --days N（N 可为负数，按天平移）或 --to YYYY-MM-DD（移到目标日期）",
        "err_move_zero": "移动天数不能为 0",
        "warn_move_series": "⚠️ 该日程是定期系列，移动将改变整个系列的所有出现",
        "warn_move_occ": "⚠️ 该日程是系列的一次出现，移动仅影响本次（若跨过相邻出现将报错）",
        "confirm_move": "📋 将移动「{s}」至 {range}",
        "move_allday_suffix": "（全天）",
        "move_success": "\n✅ 已移动:",
        # ── next ──
        "err_not_recurring": "该日程不是定期事件，没有「下次出现」",
        "next_title": "下次出现",
        "next_ended": "该系列已结束（365 天内无下次出现）",
        # ── free ──
        "free_none": "📅 {d}：无空闲时段",
        "free_all": "📅 {d}：整天空闲",
        "free_slots": "📅 {d}：{parts} 空闲",
        "err_time_hhmm": "时间格式错误: {s!r}（应为 HH:MM）",
        "err_to_from": "--to ({to}) 必须晚于 --from ({from})",
        "err_days_min": "--days 必须 ≥ 1",
        # ── 时间解析 ──
        "err_time_empty": "时间不能为空",
        "err_time_date": "时间格式错误: {s!r}（应为 YYYY-MM-DD）",
        "err_time_dt": "时间格式错误: {s!r}（应为 YYYY-MM-DD HH:MM，如 2026-08-10 09:00）",
        "err_time_both": "时间格式错误: {s!r}（应为 YYYY-MM-DD 或 YYYY-MM-DD HH:MM）",
        "warn_unknown_tz": "⚠️ 未知时区 {tz}，已按 UTC 处理",
        "warn_offset_tz": "⚠️ 无法确定系统时区名，已按当前偏移 {name} 处理（夏令时地区可能差一小时，建议设置 TZ 环境变量）",
        "warn_tz_utc": "⚠️ 无法确定系统时区，日程时间可能不正确；请设置 TZ 环境变量（如 TZ=Asia/Shanghai）后重试",
        "warn_dst_nonexistent": "⚠️ 本地时间 {t} 在夏令时切换中不存在，服务端可能按跳变后的时间调整",
        # ── Graph / 认证 ──
        "setup_hint": "python outlook_setup.py（无参数即内置应用；如需自带应用: outlook_setup.py <应用ID>）",
        "err_network_maybe": "网络错误: {e}\n   若请求可能已提交，请先 list 确认，不要盲目重试",
        "err_network": "网络错误: {e}\n   请检查网络连接后重试。",
        "err_login_expired": "登录已过期，请重新认证: {hint}",
        "err_crossing": "修改后的时间与系列中相邻出现冲突，请调整时间（不得早于前一次、晚于后一次出现）",
        "err_not_found": "该日程不存在或已被删除（定期系列已删除的某次出现不可再访问，请重新 list 确认）",
        "err_api": "API 错误 {code}: {msg}",
        "err_token_corrupt": "token 文件损坏，请重新认证:\n   {hint}",
        "err_no_refresh": "登录已过期（没有 refresh token），请重新认证:\n   {hint}",
        "err_no_client_id": "缺少应用ID，无法自动续期。请重新认证:\n   {hint}\n   或设置环境变量 OUTLOOK_CLIENT_ID",
        "err_no_msal": "缺少 msal 库，无法自动续期登录。请先安装:\n   pip install msal requests",
        "err_refresh_invalid": "登录已过期（refresh token 失效），请重新认证:\n   python outlook_setup.py（无参数即内置应用）",
        "err_refresh_fail": "刷新登录失败 ({error}): {desc}",
        # ── 定期规则 ──
        "rec_daily": "每天",
        "rec_every_n_days": "每{n}天",
        "rec_weekdays": "每个工作日",
        "rec_week_n_weekdays": "每{n}周每个工作日",
        "rec_weekly": "每周",
        "rec_every_n_weeks": "每{n}周",
        "rec_monthly_day": "每月{day}日",
        "rec_monthly_idx": "每月{idx}个{day}",
        "rec_yearly": "每年{m}月{d}日",
        "rec_count": "（共{n}次）",
        "rec_until": "（至{d}）",
        "rec_day_join": "+",
        "err_repeat_unparseable": "无法理解重复规则「{r}」。支持: 每天/每N天/每周X/每N周X/工作日/每月N日/每月第N个周X/每年X月X日",
        "err_repeat_until_fmt": "重复截止日期格式错误: {d}（应为 YYYY-MM-DD）",
        "err_repeat_until_before": "重复截止日期 {u} 早于开始日期 {s}，请调整",
        "err_repeat_count": "重复次数必须 ≥ 1",
        # ── 依赖自检（ocal_bootstrap）──
        "deps_missing": "🔧 首次运行需要安装依赖: {pkgs}",
        "deps_installing": "   正在自动安装（python -m pip install）...",
        "deps_done": "✅ 依赖安装完成: {pkgs}",
        "deps_fail": "❌ 依赖安装失败: {e}",
        "deps_fail_code": "❌ 依赖安装失败（退出码 {code}）",
        "deps_manual": "   请手动运行: {cmd}",
        "deps_still_missing": "❌ 依赖仍缺失: {pkgs}（可能需要重启终端后重试）",
        # ── 帮助文本（argparse）──
        "desc_main": "Outlook 日历助手",
        "epilog": "示例: python outlook_cal.py list --days 30",
        "help_json": "输出 JSON（机器可读）；人类提示走 stderr",
        "help_lang": "输出语言: zh/en（默认自动检测）",
        "help_status": "查看连接状态",
        "help_list": "查看日程",
        "help_days": "查看未来多少天 (默认7)",
        "help_past": "同时查看过去多少天",
        "help_search": "按标题关键词筛选",
        "help_category": "按类别筛选 (如: 工作)",
        "help_from": "从指定日期 (YYYY-MM-DD) 开始查看（此时忽略 --past）",
        "help_created_after": "只显示在此日期之后添加的日程 (YYYY-MM-DD)",
        "help_reminders": "只看设置了提醒的日程",
        "help_summary": "只按天汇总条数，不显示明细",
        "help_today": "查看今天的安排",
        "help_tomorrow": "查看明天的安排",
        "help_week": "查看今天起7天的安排",
        "help_add": "添加日程",
        "help_subject": "日程标题",
        "help_start": "开始时间 (日期 或 日期 时间)",
        "help_end": "结束时间（全天日程给结束日期表示多天，如 2026-08-12）",
        "help_all_day": "全天日程",
        "help_location": "地点",
        "help_body": "备注",
        "help_category_arg": "类别，逗号分隔多个 (如: 工作,重要)",
        "help_remind": "提醒：全天日程为提前天数，时段日程为提前分钟数",
        "help_repeat": "定期规则 (如: 每天/工作日/每周五/每月15日/每月最后一个周五/每年9月21日)",
        "help_repeat_until": "定期结束日期 (YYYY-MM-DD)",
        "help_repeat_times": "定期总次数",
        "help_importance": "重要度",
        "help_private": "设为私密",
        "help_busy": "忙闲显示状态",
        "help_force": "跳过冲突检查",
        "help_update": "更新已有日程",
        "help_event_id": "日程ID",
        "help_new_subject": "新标题",
        "help_new_start": "新开始时间 (全天: YYYY-MM-DD; 时段: YYYY-MM-DD HH:MM)",
        "help_new_end": "新结束时间 (YYYY-MM-DD HH:MM)",
        "help_all_day_switch": "转为全天日程",
        "help_no_all_day": "转为时段日程",
        "help_new_location": "新地点 (空字符串清除)",
        "help_new_body": "新备注",
        "help_new_category": "新类别，逗号分隔多个 (如: 工作,重要)；空字符串清除",
        "help_no_private": "取消私密",
        "help_no_remind": "清除提醒",
        "help_repeat_update": "重复规则 (如: 每天/工作日/每周五)；空字符串解除定期",
        "help_yes": "跳过确认",
        "help_read": "查看日程详情",
        "help_delete": "删除日程",
        "help_yes_delete": "跳过确认（定期事件默认仅删本次）",
        "help_series": "删除整个定期系列",
        "help_move": "移动日程（按天数平移或移到目标日期，保留时段）",
        "help_move_days": "按天数平移 (可为负数)",
        "help_move_to": "移到目标日期 (YYYY-MM-DD)",
        "help_next": "查看定期系列的下次出现",
        "help_free": "查询每天的空闲时段",
        "help_free_date": "开始日期 (YYYY-MM-DD)，默认今天",
        "help_free_from": "每天查询起始时间 (HH:MM，默认09:00)",
        "help_free_to": "每天查询结束时间 (HH:MM，默认18:00)",
        "help_free_days": "查询几天 (默认1)",
        # ── outlook_setup.py ──
        "setup_preparing": "\n🔐 正在准备安全认证...",
        "setup_fail_title": "\n❌ 认证准备失败。请检查以下几点：",
        "setup_fail_1": "   1. 应用ID 是否正确",
        "setup_fail_2": "   2. 应用是否已配置好「个人 Microsoft 帐户」权限",
        "setup_fail_3": "   3. 是否已开启「公共客户端流」",
        "setup_box_title": "请在手机上打开浏览器，访问：",
        "setup_box_code": "输入以下验证码：",
        "setup_box_login": "然后用你的 Outlook 账户登录并授权。",
        "setup_waiting": "\n⏳ 等待授权中（请在上面完成操作）……",
        "setup_success": "\n🎉 认证成功！",
        "setup_welcome": "   欢迎，{name}",
        "setup_connected": "   已连接到 {account}",
        "setup_try": "\n   💡 现在可以管理你的日历了，试试：",
        "setup_try_cmd": "      python outlook_cal.py list",
        "setup_expired": "\n⏰ 验证码已过期，请重新运行一次。",
        "setup_denied": "\n🚫 你拒绝了授权。如需使用日历功能请重新运行。",
        "setup_failed": "\n❌ 认证未完成，请重试。",
        "setup_your_account": "你的账户",
    },
    "en": {
        # ── 通用 ──
        "all_day": "All day",
        "date_range_sep": "-",
        "list_join": ", ",
        "filter_join": ", ",
        "err_auth_first": "Not authenticated: run python outlook_setup.py first",
        "err_id_required": "Event ID required (get one from list output 🆔)",
        "err_search_none": "No events match \"{s}\" (search window: past 7 days ~ next 30 days). Try another keyword, or run list with a wider range and specify the event ID",
        "err_search_multi": "\"{s}\" matches multiple events; specify an event ID or narrow the keyword:\n{list}",
        "help_search_target": "locate by keyword when no event ID is given (unique match operates directly; multiple matches list candidates)",
        "err_end_after_start": "End time must be after start time",
        "confirm_prompt": "   Confirm? [y/N] ",
        "cancel": "🚫 Cancelled",
        "cancel_eof": "\n🚫 Cancelled (non-interactive; use -y to skip confirmation)",
        "cancel_eof_delete": "\n🚫 Cancelled (non-interactive; use -y or --series)",
        "importance_line": "   ⭐ Importance: {v}",
        "private_line": "   🔒 Private",
        "showas_line": "   📊 Show as: {v}",
        "read_importance": "⭐ Importance: {v}",
        "read_private": "🔒 Private",
        "read_showas": "📊 Show as: {v}",
        "date_all_day": "   📅 {d} All day",
        # ── status ──
        "status_not_connected": "🔒 Not connected to calendar",
        "status_run_setup": "   Run first: python outlook_setup.py",
        "status_api_error": "⚠️  Calendar API error: {e}",
        "status_connected": "✅ Connected to Outlook calendar",
        "status_today": "   📅 Today: {d}",
        "status_mailbox_tz": "   🌐 Mailbox timezone: {tz} (differs from this computer; all-day events are written in it)",
        "status_expiry": "   🔑 Login valid for: {h}h {m}m",
        "status_expired_auto": "   🔑 Login expired; will refresh automatically on next operation",
        # ── list / 显示 ──
        "list_empty": "\n✨ {title}: no matching events\n",
        "list_header": "\n📅 {title}:\n",
        "list_count": "  {d}: {n} items",
        "rec_cancelled": " 🔁(cancelled)",
        "rec_modified": " 🔁(modified)",
        "rec_series": " 🔁(series)",
        "title_from": "Schedule from {d} ({n} days)",
        "title_range": "Past {p} days to next {n} days",
        "title_next": "Next {n} days",
        "title_created": "Events added after {d}",
        "suffix_reminders": " (with reminders only)",
        "filter_contains": "contains \"{s}\"",
        "filter_category": "category \"{c}\"",
        "filter_suffix": " (filter: {c})",
        "list_no_match": "🔍 {n} events in total, {title}: no match\n",
        # ── add ──
        "add_allday_hint": "ℹ️ No time provided; treated as all-day (use YYYY-MM-DD HH:MM for a time slot)",
        "err_repeat_until": "Repeat until/count requires --repeat",
        "err_remind_negative": "Reminder time cannot be negative",
        "err_allday_remind_max": "All-day reminder supports at most {n} days (got {m})",
        "remind_days": "Remind {n} days before",
        "remind_minutes": "Remind {n} minutes before",
        "conflict_header": "\n⚠️ Overlaps with existing events (ignore to proceed):",
        "add_success": "\n✅ Added to calendar:",
        # ── update ──
        "err_series_rule": "This is one occurrence of a series; to change the series rule, first `read` for the 🆕 series master event ID, then update the master",
        "warn_repeat_removed": "⚠️ Recurrence removed; this event is now a single event",
        "warn_repeat_reset": "⚠️ Changing the series rule resets deleted/modified exceptions of this series",
        "warn_nothing_to_update": "⚠️ Nothing to update (specify --subject/--start/--end/--all-day/-l/-b/--category/--importance/--private/--busy/--remind/--repeat)",
        "warn_occurrence_only": "⚠️ This is one occurrence of a series; this change affects only this occurrence (creates an exception), not the whole series",
        "confirm_update": "📋 Will update \"{s}\": {changes}",
        "update_success": "\n✅ Updated:",
        "ch_subject": "subject",
        "ch_allday_date": "all-day date",
        "ch_time": "time",
        "ch_location": "location",
        "ch_body": "body",
        "ch_category": "category",
        "ch_importance": "importance",
        "ch_private": "privacy",
        "ch_busy": "busy status",
        "ch_reminder": "reminder",
        "ch_recurrence": "recurrence",
        # ── read ──
        "read_added": "🕘 Added: {t}",
        "read_organizer": "👤 Organizer: {a}",
        "read_series": "🔁 Series: {s} ({rec})",
        "read_occ_num": "   This is occurrence #{n} of the series; updates/deletes affect only this occurrence",
        "read_master_id": "🆕 Series master event ID: {id}",
        "read_series_fail": "🔁 Belongs to a recurring series (failed to read master)",
        # ── delete ──
        "warn_occ_of_series": "⚠️ This event is one occurrence of series \"{s}\"",
        "delete_choice": "   [1] Delete this occurrence only   [2] Delete the whole series",
        "delete_prompt": "   Choose (default 1): ",
        "warn_series_all": "⚠️ This is the whole recurring series; deleting removes every occurrence!",
        "confirm_delete": "📋 Will delete \"{s}\"",
        "deleted_series": "🗑️ Removed the whole series \"{s}\" (all occurrences)",
        "deleted_occurrence": "🗑️ Removed this occurrence \"{s}\" (other occurrences kept)",
        "deleted_single": "🗑️ Removed \"{s}\" from the calendar",
        "delete_recoverable": "   💡 Tip: recently deleted events are still recoverable from Outlook's Deleted Items for a while",
        # ── move ──
        "err_days_to": "--days and --to cannot be used together",
        "err_move_args": "Specify --days N (can be negative, shift by days) or --to YYYY-MM-DD (move to a date)",
        "err_move_zero": "Move days cannot be 0",
        "warn_move_series": "⚠️ This event is a recurring series; moving changes every occurrence",
        "warn_move_occ": "⚠️ This is one occurrence; moving affects only this one (error if it crosses an adjacent occurrence)",
        "confirm_move": "📋 Will move \"{s}\" to {range}",
        "move_allday_suffix": " (all day)",
        "move_success": "\n✅ Moved:",
        # ── next ──
        "err_not_recurring": "This event is not recurring; it has no \"next occurrence\"",
        "next_title": "Next occurrence",
        "next_ended": "This series has ended (no occurrence within 365 days)",
        # ── free ──
        "free_none": "📅 {d}: no free slots",
        "free_all": "📅 {d}: free all day",
        "free_slots": "📅 {d}: free {parts}",
        "err_time_hhmm": "Invalid time format: {s!r} (expected HH:MM)",
        "err_to_from": "--to ({to}) must be after --from ({from})",
        "err_days_min": "--days must be ≥ 1",
        # ── 时间解析 ──
        "err_time_empty": "Time cannot be empty",
        "err_time_date": "Invalid time format: {s!r} (expected YYYY-MM-DD)",
        "err_time_dt": "Invalid time format: {s!r} (expected YYYY-MM-DD HH:MM, e.g. 2026-08-10 09:00)",
        "err_time_both": "Invalid time format: {s!r} (expected YYYY-MM-DD or YYYY-MM-DD HH:MM)",
        "warn_unknown_tz": "⚠️ Unknown timezone {tz}; using UTC",
        "warn_offset_tz": "⚠️ Could not determine the system timezone name; using current offset {name} (DST regions may be off by one hour; consider setting the TZ environment variable)",
        "warn_tz_utc": "⚠️ Could not determine the system timezone; event times may be wrong. Set the TZ environment variable (e.g. TZ=Asia/Shanghai) and retry",
        "warn_dst_nonexistent": "⚠️ Local time {t} does not exist due to a DST transition; the server may adjust it to the shifted time",
        # ── Graph / 认证 ──
        "setup_hint": "python outlook_setup.py (no args = built-in app; own app: outlook_setup.py <App ID>)",
        "err_network_maybe": "Network error: {e}\n   If the request may have been submitted, run list first to verify; don't blindly retry",
        "err_network": "Network error: {e}\n   Check your network connection and retry.",
        "err_login_expired": "Login expired; re-authenticate: {hint}",
        "err_crossing": "The new time conflicts with an adjacent occurrence in the series; adjust it (must be after the previous and before the next occurrence)",
        "err_not_found": "This event does not exist or was deleted (a deleted occurrence of a series is no longer accessible; run list again to check)",
        "err_api": "API error {code}: {msg}",
        "err_token_corrupt": "Token file corrupted; re-authenticate:\n   {hint}",
        "err_no_refresh": "Login expired (no refresh token); re-authenticate:\n   {hint}",
        "err_no_client_id": "Missing app ID; cannot refresh automatically. Re-authenticate:\n   {hint}\n   or set env OUTLOOK_CLIENT_ID",
        "err_no_msal": "Missing msal library; cannot refresh login. Install it:\n   pip install msal requests",
        "err_refresh_invalid": "Login expired (refresh token invalid); re-authenticate:\n   python outlook_setup.py",
        "err_refresh_fail": "Failed to refresh login ({error}): {desc}",
        # ── 定期规则 ──
        "rec_daily": "Daily",
        "rec_every_n_days": "Every {n} days",
        "rec_weekdays": "Every weekday",
        "rec_week_n_weekdays": "Every {n} weeks on weekdays",
        "rec_weekly": "Weekly on ",
        "rec_every_n_weeks": "Every {n} weeks on ",
        "rec_monthly_day": "Monthly on day {day}",
        "rec_monthly_idx": "Monthly on the {idx} {day}",
        "rec_yearly": "Yearly on {m}/{d}",
        "rec_count": " ({n} occurrences)",
        "rec_until": " (until {d})",
        "rec_day_join": ", ",
        "err_repeat_unparseable": "Cannot understand repeat rule \"{r}\". Supported: daily / every N days / every weekday / weekly / monthly on day N / yearly on M/D",
        "err_repeat_until_fmt": "Invalid repeat end date: {d} (expected YYYY-MM-DD)",
        "err_repeat_until_before": "Repeat end date {u} is before start date {s}; adjust it",
        "err_repeat_count": "Repeat count must be ≥ 1",
        # ── 依赖自检（ocal_bootstrap）──
        "deps_missing": "🔧 First run: installing dependencies: {pkgs}",
        "deps_installing": "   Auto-installing (python -m pip install)...",
        "deps_done": "✅ Dependencies installed: {pkgs}",
        "deps_fail": "❌ Failed to install dependencies: {e}",
        "deps_fail_code": "❌ Failed to install dependencies (exit code {code})",
        "deps_manual": "   Please run manually: {cmd}",
        "deps_still_missing": "❌ Dependencies still missing: {pkgs} (restart the terminal and retry)",
        # ── 帮助文本（argparse）──
        "desc_main": "Outlook calendar assistant",
        "epilog": "Examples: python outlook_cal.py list --days 30",
        "help_json": "Output JSON (machine-readable); human messages go to stderr",
        "help_lang": "Output language: zh/en (default: auto-detect)",
        "help_status": "Check connection status",
        "help_list": "List events",
        "help_days": "How many days ahead (default 7)",
        "help_past": "Also look back this many days",
        "help_search": "Filter by title keyword",
        "help_category": "Filter by category (e.g. work)",
        "help_from": "Start from this date (YYYY-MM-DD; ignores --past)",
        "help_created_after": "Only events added after this date (YYYY-MM-DD)",
        "help_reminders": "Only events with reminders set",
        "help_summary": "Summarize counts per day only",
        "help_today": "View today's schedule",
        "help_tomorrow": "View tomorrow's schedule",
        "help_week": "View the next 7 days from today",
        "help_add": "Add an event",
        "help_subject": "Event title",
        "help_start": "Start (date or date time)",
        "help_end": "End (for all-day: an end date makes it multi-day, e.g. 2026-08-12)",
        "help_all_day": "All-day event",
        "help_location": "Location",
        "help_body": "Notes",
        "help_category_arg": "Category, comma-separated (e.g. work,important)",
        "help_remind": "Reminder: days before for all-day, minutes before for timed",
        "help_repeat": "Repeat rule (e.g. daily/weekdays/every friday/monthly on day 15/yearly on 9/21)",
        "help_repeat_until": "Repeat end date (YYYY-MM-DD)",
        "help_repeat_times": "Repeat total count",
        "help_importance": "Importance",
        "help_private": "Mark as private",
        "help_busy": "Busy/free status",
        "help_force": "Skip conflict check",
        "help_update": "Update an event",
        "help_event_id": "Event ID",
        "help_new_subject": "New title",
        "help_new_start": "New start (all-day: YYYY-MM-DD; timed: YYYY-MM-DD HH:MM)",
        "help_new_end": "New end (YYYY-MM-DD HH:MM)",
        "help_all_day_switch": "Convert to all-day",
        "help_no_all_day": "Convert to timed",
        "help_new_location": "New location (empty clears)",
        "help_new_body": "New notes",
        "help_new_category": "New category, comma-separated; empty clears",
        "help_no_private": "Not private",
        "help_no_remind": "Clear reminder",
        "help_repeat_update": "Repeat rule (e.g. daily/weekdays/every friday); empty clears",
        "help_yes": "Skip confirmation",
        "help_read": "View event details",
        "help_delete": "Delete an event",
        "help_yes_delete": "Skip confirmation (series: delete this occurrence only by default)",
        "help_series": "Delete the whole series",
        "help_move": "Move an event (shift by days or to a date, keeping the time slot)",
        "help_move_days": "Shift by days (can be negative)",
        "help_move_to": "Move to date (YYYY-MM-DD)",
        "help_next": "View the next occurrence of a series",
        "help_free": "Query free time slots per day",
        "help_free_date": "Start date (YYYY-MM-DD), default today",
        "help_free_from": "Query from (HH:MM, default 09:00)",
        "help_free_to": "Query to (HH:MM, default 18:00)",
        "help_free_days": "How many days (default 1)",
        # ── outlook_setup.py ──
        "setup_preparing": "\n🔐 Preparing secure authentication...",
        "setup_fail_title": "\n❌ Authentication setup failed. Check:",
        "setup_fail_1": "   1. App ID is correct",
        "setup_fail_2": "   2. App has \"Personal Microsoft accounts\" permission",
        "setup_fail_3": "   3. Public client flow is enabled",
        "setup_box_title": "On your phone, open a browser and go to:",
        "setup_box_code": "Enter this code:",
        "setup_box_login": "Then sign in with your Outlook account and consent.",
        "setup_waiting": "\n⏳ Waiting for authorization (complete the steps above)…",
        "setup_success": "\n🎉 Authenticated successfully!",
        "setup_welcome": "   Welcome, {name}",
        "setup_connected": "   Connected to {account}",
        "setup_try": "\n   💡 You can now manage your calendar. Try:",
        "setup_try_cmd": "      python outlook_cal.py list",
        "setup_expired": "\n⏰ The code expired. Run it again.",
        "setup_denied": "\n🚫 You declined authorization. Run again to use the calendar.",
        "setup_failed": "\n❌ Authentication incomplete. Try again.",
        "setup_your_account": "your account",
    },
}

# ── 语言相关格式 ──────────────────────────────────
# 这些函数在调用时读取当前语言（模块加载后可能被 set_lang 改变），不能做成常量。

def t(key, **fmt):
    """按当前语言查字符串表。

    表里没有这个键就退回中文，再没有就原样显示键名——开发期能立刻发现漏翻。

    :param key: 字符串表的键
    :param fmt: 模板里 {name} 占位符的填充值
    :return: 翻译后的字符串
    """
    table = T.get(get_lang())
    s = table.get(key) if table else None
    if s is None:
        s = T["zh"].get(key, key)
    return s.format(**fmt) if fmt else s


def d_md(d):
    """短日期显示：zh 用 08月10日，en 用 08/10。

    中文年月日用手工拼接而不是写进 strftime 格式串：Windows 上 Python 3.12
    之前把格式串按 locale 编码传给 C 库，含中文的格式串会抛 UnicodeEncodeError。

    :param d: date/datetime 对象
    :return: 日期字符串
    """
    if get_lang() == "zh":
        return f"{d.strftime('%m')}月{d.strftime('%d')}日"
    return d.strftime("%m/%d")


def d_ymd(d):
    """带年份的日期显示：2026年08月10日 / 2026-08-10。

    中文年月日用手工拼接而不是写进 strftime 格式串，原因同 d_md。

    :param d: date/datetime 对象
    :return: 日期字符串
    """
    if get_lang() == "zh":
        return f"{d.strftime('%Y')}年{d.strftime('%m')}月{d.strftime('%d')}日"
    return d.strftime("%Y-%m-%d")


def weekday(d):
    """星期短名：周一 / Mon。

    :param d: date/datetime 对象
    :return: 星期字符串
    """
    zh = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")
    en = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
    names = zh if get_lang() == "zh" else en
    return names[d.weekday()]


def date_weekday(d, with_year=False):
    """日期和星期拼一起：08月10日 周一 / 08/10 Mon。

    :param d: date/datetime 对象
    :param with_year: True 时日期带年份
    :return: 组合字符串
    """
    fmt = d_ymd if with_year else d_md
    return f"{fmt(d)} {weekday(d)}"


def all_day():
    """全天/All day 的当前语言写法。

    :return: "全天" 或 "All day"
    """
    return t("all_day")


def join(parts):
    """用当前语言的列表连接符拼字符串（zh 用 、，en 用 ", "）。

    :param parts: 可迭代的字符串
    :return: 拼接结果
    """
    return t("list_join").join(parts)


def range_sep():
    """日期范围中间用的连接符。

    :return: "~"（zh）或 "-"（en）
    """
    return t("date_range_sep")


def weekday_names():
    """一周七天的名称（周一起，和 Python weekday() 对齐）。

    :return: 7 个名称的列表
    """
    zh = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    en = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return zh if get_lang() == "zh" else en


def idx_name(k):
    """把英文序数词（first/second/...）翻成当前语言。

    :param k: first / second / third / fourth / last
    :return: 当前语言的写法
    """
    zh = {"first": "第一", "second": "第二", "third": "第三", "fourth": "第四", "last": "最后"}
    en = {"first": "first", "second": "second", "third": "third", "fourth": "fourth", "last": "last"}
    m = zh if get_lang() == "zh" else en
    return m.get(k, k)


def imp_name(k):
    """重要度的显示值：zh 时 low/high 显示成 低/高，en 保持原样。

    :param k: low / normal / high
    :return: 显示用字符串
    """
    if get_lang() == "zh":
        return {"low": "低", "high": "高"}.get(k, k)
    return k
