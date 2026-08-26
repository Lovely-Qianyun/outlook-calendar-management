"""ocal_recurrence — 定期规则：自然语言解析、人类可读格式化、出现次数估算、参数构造。"""
from datetime import datetime, timedelta

from ocal_errors import CalError
from ocal_i18n import t, get_lang, idx_name, weekday_names
from ocal_time import LOCAL_TZ_NAME

# 注意：Python weekday() 0=周一 ... 6=周日，这两个数组必须从周一对齐
EN_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
CN_DAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
WEEK_INDEX = {"first": "第一", "second": "第二", "third": "第三", "fourth": "第四", "last": "最后"}

# 英文星期解析别名（"every friday" 用）
_EN_WEEKDAY_RE = "|".join(EN_DAYS)


def _parse_recurrence(desc, start_date):
    """把自然语言重复描述解析成 Graph 的 recurrence 对象。

    中文支持：每天 / 每N天 / 每周X / 每N周X / 工作日 / 每月N日 / 每月第N个周X / 每年X月X日
    英文支持：daily / every day / every N days / weekdays / every weekday / every friday / weekly / monthly on day N / yearly on M/D

    :param desc: 用户给的重复规则描述
    :param start_date: 开始日期（"每周"没给星期时用它推断默认星期）
    :return: (recurrence dict, 人类可读描述)；不认识的规则返回 (None, None)
    """
    import re as _re
    s = desc.strip().lower()
    pattern = {}
    if s in ("每天", "每日", "daily", "every day"):
        pattern = {"type": "daily", "interval": 1}
        desc_cn = t("rec_daily")
    elif s in ("工作日", "每个工作日", "每周工作日", "工作日每天", "every weekday", "every workday", "mon-fri", "weekdays"):
        # 周一至周五：必须在 weekly 分支之前判断，否则"每周工作日"会被 weekly 误吞
        pattern = {"type": "weekly", "interval": 1,
                   "daysOfWeek": ["monday", "tuesday", "wednesday", "thursday", "friday"]}
        desc_cn = t("rec_weekdays")
    elif _re.match(r"^每(\d+)天$", s):
        interval = int(_re.match(r"^每(\d+)天$", s).group(1))
        if interval < 1:
            return None, None  # 每0天没有意义，别等 Graph 拒绝
        pattern = {"type": "daily", "interval": interval}
        desc_cn = t("rec_every_n_days", n=pattern['interval'])
    elif _re.match(r"^every (\d+) days$", s):
        interval = int(_re.match(r"^every (\d+) days$", s).group(1))
        if interval < 1:
            return None, None
        pattern = {"type": "daily", "interval": interval}
        desc_cn = t("rec_every_n_days", n=pattern['interval'])
    elif s in ("每周", "每周一", "weekly") or _re.match(r"^每\d*周", s):
        m = _re.match(r"^每(\d*)周(.*)$", s)
        interval = int(m.group(1)) if m and m.group(1) else 1
        if interval < 1:
            return None, None  # 每0周同理
        rest = m.group(2) if m else s.replace("每周", "").replace("weekly", "")
        days = []
        if not rest:
            # 没写星期：从 start_date 推断
            days = [EN_DAYS[start_date.weekday()]]
            desc_cn = (t("rec_weekly") if interval == 1 else t("rec_every_n_weeks", n=interval)) \
                + weekday_names()[start_date.weekday()]
        else:
            for i, cn in enumerate(CN_DAYS):
                if cn.replace("周", "") in rest or cn in rest:
                    days.append(EN_DAYS[i])
            if not days:
                return None, None
            day_strs = t("rec_day_join").join(weekday_names()[i] for i, d in enumerate(EN_DAYS) if d in days)
            desc_cn = (t("rec_weekly") if interval == 1 else t("rec_every_n_weeks", n=interval)) + day_strs
        pattern = {"type": "weekly", "interval": interval, "daysOfWeek": days}
    elif _re.match(rf"^every ({_EN_WEEKDAY_RE})$", s):
        # 英文单日：every friday
        day = _re.match(rf"^every ({_EN_WEEKDAY_RE})$", s).group(1)
        pattern = {"type": "weekly", "interval": 1, "daysOfWeek": [day]}
        desc_cn = t("rec_weekly") + weekday_names()[EN_DAYS.index(day)]
    elif _re.match(r"^每月(\d+)日", s):
        m = _re.match(r"^每月(\d+)日", s)
        day = int(m.group(1))
        if not 1 <= day <= 31:
            return None, None
        pattern = {"type": "absoluteMonthly", "interval": 1, "dayOfMonth": day}
        desc_cn = t("rec_monthly_day", day=day)
    elif _re.match(r"^monthly on day (\d+)$", s):
        day = int(_re.match(r"^monthly on day (\d+)$", s).group(1))
        if not 1 <= day <= 31:
            return None, None
        pattern = {"type": "absoluteMonthly", "interval": 1, "dayOfMonth": day}
        desc_cn = t("rec_monthly_day", day=day)
    elif _re.match(r"^每月(第一|第二|第三|第四|最后)(一)?个(周[一二三四五六日]|星期[一二三四五六日])", s):
        m = _re.match(r"^每月(第一|第二|第三|第四|最后)(一)?个(周[一二三四五六日]|星期[一二三四五六日])", s)
        idx_map = {"第一": "first", "第二": "second", "第三": "third", "第四": "fourth", "最后": "last"}
        day_part = m.group(3).replace("星期", "").replace("周", "")
        day_idx = CN_DAYS.index("周" + day_part)
        pattern = {"type": "relativeMonthly", "interval": 1, "index": idx_map[m.group(1)], "daysOfWeek": [EN_DAYS[day_idx]]}
        desc_cn = t("rec_monthly_idx", idx=idx_name(idx_map[m.group(1)]), day=weekday_names()[day_idx])
        if get_lang() == "zh":
            desc_cn = desc_cn.replace("最后个", "最后一个")
    elif _re.match(r"^每年(\d+)月(\d+)日", s):
        m = _re.match(r"^每年(\d+)月(\d+)日", s)
        month, day = int(m.group(1)), int(m.group(2))
        if not (1 <= month <= 12 and 1 <= day <= 31):
            return None, None
        pattern = {"type": "absoluteYearly", "interval": 1, "dayOfMonth": day, "month": month}
        desc_cn = t("rec_yearly", m=month, d=day)
    elif _re.match(r"^yearly on (\d{1,2})/(\d{1,2})$", s):
        m = _re.match(r"^yearly on (\d{1,2})/(\d{1,2})$", s)
        month, day = int(m.group(1)), int(m.group(2))
        if not (1 <= month <= 12 and 1 <= day <= 31):
            return None, None
        pattern = {"type": "absoluteYearly", "interval": 1, "dayOfMonth": day, "month": month}
        desc_cn = t("rec_yearly", m=month, d=day)
    else:
        return None, None

    recurrence = {
        "pattern": pattern,
        "range": {
            "type": "noEnd",
            "startDate": start_date.strftime("%Y-%m-%d"),
        },
    }
    return recurrence, desc_cn


def _fmt_recurrence(rec):
    """把 recurrence 对象翻译成人话（read/list 里显示用）。

    :param rec: Graph 的 recurrence 对象
    :return: 人类可读描述；空对象返回空串
    """
    if not rec:
        return ""
    p = rec.get("pattern", {})
    r = rec.get("range", {})
    ttype = p.get("type", "")
    interval = p.get("interval", 1)
    names = weekday_names()
    if ttype == "daily":
        desc = t("rec_daily") if interval == 1 else t("rec_every_n_days", n=interval)
    elif ttype == "weekly":
        days = [names[i] for i, d in enumerate(EN_DAYS) if d in p.get("daysOfWeek", [])]
        if p.get("daysOfWeek") and set(p["daysOfWeek"]) == {"monday", "tuesday", "wednesday", "thursday", "friday"}:
            # 周一至周五 = 每个工作日
            desc = t("rec_weekdays") if interval == 1 else t("rec_week_n_weekdays", n=interval)
        else:
            head = t("rec_weekly") if interval == 1 else t("rec_every_n_weeks", n=interval)
            desc = head + t("rec_day_join").join(days)
    elif ttype == "absoluteMonthly":
        desc = t("rec_monthly_day", day=p.get('dayOfMonth', '?'))
    elif ttype == "relativeMonthly":
        idx = idx_name(p.get("index", ""))
        days = [names[i] for i, d in enumerate(EN_DAYS) if d in p.get("daysOfWeek", [])]
        desc = t("rec_monthly_idx", idx=idx, day=days[0] if days else '?')
        if get_lang() == "zh":
            desc = desc.replace("最后个", "最后一个")
    elif ttype == "absoluteYearly":
        desc = t("rec_yearly", m=p.get('month', '?'), d=p.get('dayOfMonth', '?'))
    else:
        desc = ttype
    rtype = r.get("type", "")
    if rtype == "numbered":
        desc += t("rec_count", n=r.get('numberOfOccurrences', '?'))
    elif rtype == "endDate":
        desc += t("rec_until", d=r.get('endDate', '?'))
    return desc


def _occurrence_number(rec, occ_dt):
    """数一下 occ 在系列里是第几次出现；算不出来返回 None。

    从 range.startDate 按周期一天天数过去（上限 3650 天防死循环），
    不调 /instances 端点——省一次请求，也躲开它的分页问题。

    :param rec: recurrence 对象
    :param occ_dt: 某个出现的 start.dateTime
    :return: 第 N 次（从 1 起）；无法计算返回 None
    """
    if not rec or not occ_dt:
        return None
    try:
        p = rec.get('pattern', {})
        r = rec.get('range', {})
        start = datetime.strptime(r.get('startDate', '')[:10], "%Y-%m-%d").date()
        occ = datetime.strptime(occ_dt[:10], "%Y-%m-%d").date()
    except Exception:
        return None
    ttype = p.get('type', '')
    interval = max(p.get('interval', 1), 1)
    if occ < start:
        return None
    if ttype == 'daily':
        return (occ - start).days // interval + 1
    if ttype == 'weekly':
        days = set(p.get('daysOfWeek', []))
        if not days:
            return None
        n = 1
        d = start
        while d <= occ:
            if (d - start).days > 3650:
                return None
            if ((d - start).days // 7) % interval == 0 and EN_DAYS[d.weekday()] in days:
                if d == occ:
                    return n
                n += 1
            d += timedelta(days=1)
        return None
    if ttype in ('absoluteMonthly', 'relativeMonthly'):
        return (occ.year - start.year) * 12 + (occ.month - start.month) + 1
    if ttype == 'absoluteYearly':
        return occ.year - start.year + 1
    return None

def _build_recurrence(repeat, repeat_until, repeat_times, start_dt):
    """按命令行参数拼定期规则（解析 + 结束条件），add/update 共用。

    :param repeat: 规则描述
    :param repeat_until: 结束日期（YYYY-MM-DD），可空
    :param repeat_times: 总次数，可空
    :param start_dt: 开始时间（用来定 range.startDate）
    :return: (recurrence dict, 人类可读描述)
    :raises CalError: 规则看不懂 / 结束条件非法
    """
    recurrence, desc_cn = _parse_recurrence(repeat, start_dt)
    if not recurrence:
        raise CalError(t("err_repeat_unparseable", r=repeat))
    # Graph 对定期事件若不显式指定 recurrenceTimeZone 会默认按 UTC 锚定循环，
    # 结果 originalStartTimeZone=UTC 而 originalEndTimeZone=本地时区，Outlook
    # 显示"开始是 UTC、结束是本地时间"。这里与 start/end 的 timeZone 保持一致
    recurrence["range"]["recurrenceTimeZone"] = LOCAL_TZ_NAME
    if repeat_until is not None:
        try:
            until = datetime.strptime(repeat_until, "%Y-%m-%d")
        except ValueError:
            raise CalError(t("err_repeat_until_fmt", d=repeat_until))
        if until.date() < start_dt.date():
            raise CalError(t("err_repeat_until_before", u=repeat_until, s=start_dt.date()))
        recurrence["range"]["type"] = "endDate"
        recurrence["range"]["endDate"] = until.strftime("%Y-%m-%d")
    elif repeat_times is not None:
        if repeat_times < 1:
            raise CalError(t("err_repeat_count"))
        recurrence["range"]["type"] = "numbered"
        recurrence["range"]["numberOfOccurrences"] = repeat_times
    return recurrence, desc_cn
