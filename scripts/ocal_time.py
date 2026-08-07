"""ocal_time — 时区与时间：本地时区探测、Graph 时间字符串解析、时间参数校验。"""
import sys
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

from ocal_errors import CalError
from ocal_i18n import t, weekday

# Graph 返回的时区名经常是 Windows 名（如 "China Standard Time"），先映射成 IANA 名
WINDOWS_TZ_MAP = {
    "China Standard Time": "Asia/Shanghai",
    "Taipei Standard Time": "Asia/Taipei",
    "Tokyo Standard Time": "Asia/Tokyo",
    "Korea Standard Time": "Asia/Seoul",
    "Singapore Standard Time": "Asia/Singapore",
    "India Standard Time": "Asia/Kolkata",
    "Nepal Standard Time": "Asia/Kathmandu",
    "Sri Lanka Standard Time": "Asia/Colombo",
    "Bangladesh Standard Time": "Asia/Dhaka",
    "Indochina Time": "Asia/Bangkok",
    "Malay Peninsula Standard Time": "Asia/Kuala_Lumpur",
    "Iran Standard Time": "Asia/Tehran",
    "Israel Standard Time": "Asia/Jerusalem",
    "Middle East Standard Time": "Asia/Beirut",
    "W. Central Africa Standard Time": "Africa/Lagos",
    "E. Africa Standard Time": "Africa/Nairobi",
    "South Africa Standard Time": "Africa/Johannesburg",
    "GMT Standard Time": "Europe/London",
    "W. Europe Standard Time": "Europe/Berlin",
    "Central Europe Standard Time": "Europe/Paris",
    "E. Europe Standard Time": "Europe/Bucharest",
    "Russian Standard Time": "Europe/Moscow",
    "Turkey Standard Time": "Europe/Istanbul",
    "Atlantic Standard Time": "America/Halifax",
    "Eastern Standard Time": "America/New_York",
    "Central Standard Time": "America/Chicago",
    "Mountain Standard Time": "America/Denver",
    "Pacific Standard Time": "America/Los_Angeles",
    "Pacific Standard Time (Mexico)": "America/Tijuana",
    "Alaskan Standard Time": "America/Anchorage",
    "Hawaiian Standard Time": "Pacific/Honolulu",
    "Central America Standard Time": "America/Guatemala",
    "SA Pacific Standard Time": "America/Bogota",
    "AUS Eastern Standard Time": "Australia/Sydney",
    "AUS Central Standard Time": "Australia/Darwin",
    "Cen. Australia Standard Time": "Australia/Adelaide",
    "W. Australia Standard Time": "Australia/Perth",
    "New Zealand Standard Time": "Pacific/Auckland",
    "UTC": "UTC",
}

# ── 时区处理 ──────────────────────────────────────

_warned_tz = set()  # 未知时区的警告只提示一次，不然每次格式化都刷屏


def _resolve_tz(tz_str):
    """把 Graph 的 timeZone 字符串变成 tzinfo。

    Graph 可能返回 Windows 时区名，先查表映射成 IANA 名再交给 ZoneInfo；
    实在解析不了就警告一次并按 UTC 处理（总比直接报错强）。

    :param tz_str: Graph 事件的 timeZone 字段值
    :return: tzinfo；解析失败回退 UTC
    """
    if not tz_str:
        return timezone.utc
    tz_str = tz_str.strip()
    if tz_str.upper() in ("UTC", "GMT", "Z"):
        return timezone.utc
    if tz_str in WINDOWS_TZ_MAP:
        tz_str = WINDOWS_TZ_MAP[tz_str]
    if ZoneInfo:
        try:
            return ZoneInfo(tz_str)
        except Exception:
            pass
    if tz_str not in _warned_tz:
        _warned_tz.add(tz_str)
        print(t("warn_unknown_tz", tz=tz_str), file=sys.stderr)
    return timezone.utc


def _detect_local_tz():
    """探测本机时区，返回 (tzinfo, 传给 Graph 的时区名)。

    探测顺序：Windows 注册表的 TimeZoneKeyName → 系统 tzinfo 的 IANA 名
    → 兜底用本地 tzinfo（偏移是对的），时区名给 UTC。

    :return: (tzinfo, 时区名)
    """
    tz_name = None
    # 1) Windows 注册表
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                           r"SYSTEM\CurrentControlSet\Control\TimeZoneInformation")
        tz_name, _ = winreg.QueryValueEx(k, "TimeZoneKeyName")
        winreg.CloseKey(k)
    except Exception:
        pass
    # 2) 系统 tzinfo（Linux/macOS）
    tz = datetime.now().astimezone().tzinfo
    if not tz_name:
        tz_name = getattr(tz, 'key', None)
    # Windows 名归一化成 IANA 名
    if tz_name in WINDOWS_TZ_MAP:
        tz_name = WINDOWS_TZ_MAP[tz_name]
    if ZoneInfo and tz_name:
        try:
            return ZoneInfo(tz_name), tz_name
        except Exception:
            pass
    return tz, tz_name or "UTC"


LOCAL_TZ, LOCAL_TZ_NAME = _detect_local_tz()


def _normalize_dt(s):
    """把 Graph 时间字符串修成 datetime.fromisoformat 能吃的格式。

    Graph 的时间戳可能带 7 位小数，Python 3.11 之前只认 6 位，这里截断；
    结尾的 Z 换成 +00:00。

    :param s: Graph 的 dateTime 字符串
    :return: 归一化后的字符串
    """
    s = s.replace("Z", "+00:00")
    if "." in s:
        head, frac = s.split(".", 1)
        frac = frac[:6]
        s = f"{head}.{frac}" if frac else head
    return s


def _parse_dt(dt_str, tz_str=None):
    """把 Graph 时间字符串转成本地时区的 datetime。

    :param dt_str: Graph 的 dateTime 字符串
    :param tz_str: 事件自带的 timeZone（字符串里没带偏移时用来补）
    :return: 本地时区的 aware datetime
    """
    dt = datetime.fromisoformat(_normalize_dt(dt_str))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_resolve_tz(tz_str))
    return dt.astimezone(LOCAL_TZ)


def _parse_dt_arg(s, *, date_only=False):
    """解析命令行给的时间参数；格式不对抛 CalError（友好提示，不甩 traceback）。

    :param s: 命令行时间，如 "2026-08-10" 或 "2026-08-10 09:00"
    :param date_only: True 时只收日期，不收时间
    :return: naive datetime
    :raises CalError: 时间格式无法解析
    """
    if not s:
        raise CalError(t("err_time_empty"))
    if date_only:
        try:
            return datetime.strptime(s, "%Y-%m-%d")
        except ValueError:
            raise CalError(t("err_time_date", s=s))
    if " " in s:
        try:
            return datetime.strptime(s, "%Y-%m-%d %H:%M")
        except ValueError:
            raise CalError(t("err_time_dt", s=s))
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        raise CalError(t("err_time_both", s=s))


def _all_day_range(start_str, end_str):
    """算出全天事件占的日期段（naive 解析，不做时区换算）。

    Graph 对全天事件固定 start 00:00:00、end 为末次次日 00:00（不含），
    dateTime 里的日期就是日历日期；字符串可能带 .0000000 后缀，取前 10 位规避。

    :param start_str: start.dateTime
    :param end_str: end.dateTime
    :return: (开始日期, 结束日期)，结束日期含当天
    """
    start = datetime.strptime(start_str[:10], "%Y-%m-%d").date()
    end = datetime.strptime(end_str[:10], "%Y-%m-%d").date() - timedelta(days=1)
    return start, max(end, start)


def _fmt(dt_str, tz_str=None):
    """格式化时间用于显示（MM/DD HH:MM）；解析不了就原样返回。

    :param dt_str: Graph 的 dateTime 字符串
    :param tz_str: 事件 timeZone（可空）
    :return: 显示用字符串
    """
    if not dt_str:
        return ""
    try:
        return _parse_dt(dt_str, tz_str).strftime("%m/%d %H:%M")
    except Exception:
        return dt_str


def _weekday(dt_str, tz_str=None):
    """取事件的星期（周一/Mon）；解析不了返回空串。

    :param dt_str: Graph 的 dateTime 字符串
    :param tz_str: 事件 timeZone（可空）
    :return: 星期显示名
    """
    try:
        return weekday(_parse_dt(dt_str, tz_str))
    except Exception:
        return ""
