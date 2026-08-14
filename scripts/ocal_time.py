"""ocal_time — 时区与时间：本地时区探测、Graph 时间字符串解析、时间参数校验。"""
import os
import re
import sys
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

from ocal_errors import CalError
from ocal_i18n import t, weekday

# Graph 返回的时区名经常是 Windows 名（如 "China Standard Time"），先映射成 IANA 名。
# 全量 CLDR windowsZones 映射：官方 Windows 时区名 → 规范 IANA 名。
# 缺一条就有一个地区的事件被静默按 UTC 显示（差几小时），所以这里是全表而不是精选。
WINDOWS_TZ_MAP = {
    "Dateline Standard Time": "Etc/GMT+12",
    "UTC-11": "Etc/GMT+11",
    "Aleutian Standard Time": "America/Adak",
    "Hawaiian Standard Time": "Pacific/Honolulu",
    "Marquesas Standard Time": "Pacific/Marquesas",
    "Alaskan Standard Time": "America/Anchorage",
    "UTC-09": "Etc/GMT+9",
    "Pacific Standard Time (Mexico)": "America/Tijuana",
    "UTC-08": "Etc/GMT+8",
    "Pacific Standard Time": "America/Los_Angeles",
    "US Mountain Standard Time": "America/Phoenix",
    "Mountain Standard Time (Mexico)": "America/Chihuahua",
    "Mountain Standard Time": "America/Denver",
    "Yukon Standard Time": "America/Whitehorse",
    "Central America Standard Time": "America/Guatemala",
    "Central Standard Time": "America/Chicago",
    "Easter Island Standard Time": "Pacific/Easter",
    "Central Standard Time (Mexico)": "America/Mexico_City",
    "Canada Central Standard Time": "America/Regina",
    "SA Pacific Standard Time": "America/Bogota",
    "Eastern Standard Time (Mexico)": "America/Cancun",
    "Eastern Standard Time": "America/New_York",
    "Haiti Standard Time": "America/Port-au-Prince",
    "Cuba Standard Time": "America/Havana",
    "US Eastern Standard Time": "America/Indiana/Indianapolis",
    "Turks And Caicos Standard Time": "America/Grand_Turk",
    "Paraguay Standard Time": "America/Asuncion",
    "Atlantic Standard Time": "America/Halifax",
    "Venezuela Standard Time": "America/Caracas",
    "Central Brazilian Standard Time": "America/Cuiaba",
    "SA Western Standard Time": "America/La_Paz",
    "Pacific SA Standard Time": "America/Santiago",
    "Newfoundland Standard Time": "America/St_Johns",
    "Tocantins Standard Time": "America/Araguaina",
    "E. South America Standard Time": "America/Sao_Paulo",
    "SA Eastern Standard Time": "America/Cayenne",
    "Argentina Standard Time": "America/Argentina/Buenos_Aires",
    "Greenland Standard Time": "America/Godthab",
    "Montevideo Standard Time": "America/Montevideo",
    "Magallanes Standard Time": "America/Punta_Arenas",
    "Saint Pierre Standard Time": "America/Miquelon",
    "Bahia Standard Time": "America/Bahia",
    "UTC-02": "Etc/GMT+2",
    "Azores Standard Time": "Atlantic/Azores",
    "Cape Verde Standard Time": "Atlantic/Cape_Verde",
    "UTC": "Etc/UTC",
    "GMT Standard Time": "Europe/London",
    "Greenwich Standard Time": "Atlantic/Reykjavik",
    "Sao Tome Standard Time": "Africa/Sao_Tome",
    "Morocco Standard Time": "Africa/Casablanca",
    "W. Europe Standard Time": "Europe/Berlin",
    "Central Europe Standard Time": "Europe/Budapest",
    "Romance Standard Time": "Europe/Paris",
    "Central European Standard Time": "Europe/Warsaw",
    "W. Central Africa Standard Time": "Africa/Lagos",
    "Jordan Standard Time": "Asia/Amman",
    "GTB Standard Time": "Europe/Bucharest",
    "Middle East Standard Time": "Asia/Beirut",
    "Egypt Standard Time": "Africa/Cairo",
    "E. Europe Standard Time": "Europe/Chisinau",
    "Syria Standard Time": "Asia/Damascus",
    "West Bank Standard Time": "Asia/Hebron",
    "South Africa Standard Time": "Africa/Johannesburg",
    "FLE Standard Time": "Europe/Kyiv",
    "Israel Standard Time": "Asia/Jerusalem",
    "South Sudan Standard Time": "Africa/Juba",
    "Kaliningrad Standard Time": "Europe/Kaliningrad",
    "Sudan Standard Time": "Africa/Khartoum",
    "Libya Standard Time": "Africa/Tripoli",
    "Namibia Standard Time": "Africa/Windhoek",
    "Arabic Standard Time": "Asia/Baghdad",
    "Turkey Standard Time": "Europe/Istanbul",
    "Arab Standard Time": "Asia/Riyadh",
    "Belarus Standard Time": "Europe/Minsk",
    "Russian Standard Time": "Europe/Moscow",
    "E. Africa Standard Time": "Africa/Nairobi",
    "Volgograd Standard Time": "Europe/Volgograd",
    "Iran Standard Time": "Asia/Tehran",
    "Arabian Standard Time": "Asia/Dubai",
    "Astrakhan Standard Time": "Europe/Astrakhan",
    "Azerbaijan Standard Time": "Asia/Baku",
    "Russia Time Zone 3": "Europe/Samara",
    "Mauritius Standard Time": "Indian/Mauritius",
    "Saratov Standard Time": "Europe/Saratov",
    "Georgian Standard Time": "Asia/Tbilisi",
    "Caucasus Standard Time": "Asia/Yerevan",
    "Afghanistan Standard Time": "Asia/Kabul",
    "West Asia Standard Time": "Asia/Tashkent",
    "Ekaterinburg Standard Time": "Asia/Yekaterinburg",
    "Pakistan Standard Time": "Asia/Karachi",
    "Qyzylorda Standard Time": "Asia/Qyzylorda",
    "India Standard Time": "Asia/Kolkata",
    "Sri Lanka Standard Time": "Asia/Colombo",
    "Nepal Standard Time": "Asia/Kathmandu",
    "Central Asia Standard Time": "Asia/Almaty",
    "Bangladesh Standard Time": "Asia/Dhaka",
    "Omsk Standard Time": "Asia/Omsk",
    "Myanmar Standard Time": "Asia/Yangon",
    "SE Asia Standard Time": "Asia/Bangkok",
    "Altai Standard Time": "Asia/Barnaul",
    "W. Mongolia Standard Time": "Asia/Hovd",
    "North Asia Standard Time": "Asia/Krasnoyarsk",
    "N. Central Asia Standard Time": "Asia/Novosibirsk",
    "Tomsk Standard Time": "Asia/Tomsk",
    "China Standard Time": "Asia/Shanghai",
    "North Asia East Standard Time": "Asia/Irkutsk",
    "Singapore Standard Time": "Asia/Singapore",
    "W. Australia Standard Time": "Australia/Perth",
    "Taipei Standard Time": "Asia/Taipei",
    "Ulaanbaatar Standard Time": "Asia/Ulaanbaatar",
    "Aus Central W. Standard Time": "Australia/Eucla",
    "Transbaikal Standard Time": "Asia/Chita",
    "Tokyo Standard Time": "Asia/Tokyo",
    "North Korea Standard Time": "Asia/Pyongyang",
    "Korea Standard Time": "Asia/Seoul",
    "Yakutsk Standard Time": "Asia/Yakutsk",
    "Cen. Australia Standard Time": "Australia/Adelaide",
    "AUS Central Standard Time": "Australia/Darwin",
    "E. Australia Standard Time": "Australia/Brisbane",
    "AUS Eastern Standard Time": "Australia/Sydney",
    "West Pacific Standard Time": "Pacific/Port_Moresby",
    "Tasmania Standard Time": "Australia/Hobart",
    "Vladivostok Standard Time": "Asia/Vladivostok",
    "Lord Howe Standard Time": "Australia/Lord_Howe",
    "Bougainville Standard Time": "Pacific/Bougainville",
    "Russia Time Zone 10": "Asia/Srednekolymsk",
    "Magadan Standard Time": "Asia/Magadan",
    "Norfolk Standard Time": "Pacific/Norfolk",
    "Sakhalin Standard Time": "Asia/Sakhalin",
    "Central Pacific Standard Time": "Pacific/Guadalcanal",
    "Russia Time Zone 11": "Asia/Kamchatka",
    "New Zealand Standard Time": "Pacific/Auckland",
    "UTC+12": "Etc/GMT-12",
    "Fiji Standard Time": "Pacific/Fiji",
    "Chatham Islands Standard Time": "Pacific/Chatham",
    "UTC+13": "Etc/GMT-13",
    "Tonga Standard Time": "Pacific/Tongatapu",
    "Samoa Standard Time": "Pacific/Apia",
    "Line Islands Standard Time": "Pacific/Kiritimati",
}

# 已废弃的旧 Windows 时区名（XP 时代注册表名）：只做"解析"方向的映射，
# 不参与 IANA→Windows 反查——反查必须用现行官方名，否则会挑到旧名字。
LEGACY_WINDOWS_TZ_MAP = {
    "Indochina Time": "Asia/Bangkok",
    "Malay Peninsula Standard Time": "Asia/Kuala_Lumpur",
}

# IANA → Windows 名反向映射（Graph 的 timeZone 字段用 Windows 名最稳）。
# 先反转规范表，再叠加常见非规范 IANA 别名（系统/时区库常报这些名字）。
IANA_TO_WINDOWS = {v: k for k, v in WINDOWS_TZ_MAP.items()}
IANA_TO_WINDOWS.update({
    # 中国/东亚常用别名 → China Standard Time
    "Asia/Hong_Kong": "China Standard Time",
    "Asia/Macau": "China Standard Time",
    "Asia/Chongqing": "China Standard Time",
    "Asia/Harbin": "China Standard Time",
    "Asia/Urumqi": "China Standard Time",
    "Asia/Kashgar": "China Standard Time",
    "PRC": "China Standard Time",
    "ROC": "Taipei Standard Time",
    # 欧洲常用别名
    "Europe/Amsterdam": "W. Europe Standard Time",
    "Europe/Andorra": "W. Europe Standard Time",
    "Europe/Brussels": "W. Europe Standard Time",
    "Europe/Copenhagen": "W. Europe Standard Time",
    "Europe/Gibraltar": "W. Europe Standard Time",
    "Europe/Luxembourg": "W. Europe Standard Time",
    "Europe/Madrid": "W. Europe Standard Time",
    "Europe/Malta": "W. Europe Standard Time",
    "Europe/Monaco": "W. Europe Standard Time",
    "Europe/Oslo": "W. Europe Standard Time",
    "Europe/Rome": "W. Europe Standard Time",
    "Europe/Stockholm": "W. Europe Standard Time",
    "Europe/Vaduz": "W. Europe Standard Time",
    "Europe/Vatican": "W. Europe Standard Time",
    "Europe/Vienna": "W. Europe Standard Time",
    "Europe/Zurich": "W. Europe Standard Time",
    "Europe/Bratislava": "Central Europe Standard Time",
    "Europe/Belgrade": "Central Europe Standard Time",
    "Europe/Ljubljana": "Central Europe Standard Time",
    "Europe/Podgorica": "Central Europe Standard Time",
    "Europe/Prague": "Central Europe Standard Time",
    "Europe/Sarajevo": "Central Europe Standard Time",
    "Europe/Skopje": "Central Europe Standard Time",
    "Europe/Tirana": "Central Europe Standard Time",
    "Europe/Zagreb": "Central Europe Standard Time",
    "Europe/Dublin": "GMT Standard Time",
    "Europe/Guernsey": "GMT Standard Time",
    "Europe/Isle_of_Man": "GMT Standard Time",
    "Europe/Jersey": "GMT Standard Time",
    "Europe/Lisbon": "GMT Standard Time",
    "Atlantic/Canary": "GMT Standard Time",
    "Atlantic/Faeroe": "GMT Standard Time",
    "Atlantic/Madeira": "GMT Standard Time",
    "Europe/Kiev": "FLE Standard Time",
    "Europe/Uzhgorod": "FLE Standard Time",
    "Europe/Zaporozhye": "FLE Standard Time",
    # 美洲常用别名
    "America/Toronto": "Eastern Standard Time",
    "America/Montreal": "Eastern Standard Time",
    "America/Nassau": "Eastern Standard Time",
    "America/Atikokan": "Eastern Standard Time",
    "America/Detroit": "Eastern Standard Time",
    "America/Iqaluit": "Eastern Standard Time",
    "America/Kentucky/Louisville": "Eastern Standard Time",
    "America/Nipigon": "Eastern Standard Time",
    "America/Thunder_Bay": "Eastern Standard Time",
    "America/Indiana/Knox": "Central Standard Time",
    "America/Rainy_River": "Central Standard Time",
    "America/Rankin_Inlet": "Central Standard Time",
    "America/Resolute": "Central Standard Time",
    "America/Winnipeg": "Central Standard Time",
    "America/Boise": "Mountain Standard Time",
    "America/Cambridge_Bay": "Mountain Standard Time",
    "America/Edmonton": "Mountain Standard Time",
    "America/Inuvik": "Mountain Standard Time",
    "America/Yellowknife": "Mountain Standard Time",
    "America/Vancouver": "Pacific Standard Time",
    "America/Glace_Bay": "Atlantic Standard Time",
    "America/Goose_Bay": "Atlantic Standard Time",
    "America/Moncton": "Atlantic Standard Time",
    "America/Manaus": "SA Western Standard Time",
    "America/Porto_Velho": "SA Western Standard Time",
    "America/Boa_Vista": "SA Western Standard Time",
    "America/Noronha": "UTC-02",
    "America/Indianapolis": "US Eastern Standard Time",
    # 亚洲/非洲/大洋洲常用别名
    "Asia/Calcutta": "India Standard Time",
    "Asia/Saigon": "SE Asia Standard Time",
    "Asia/Kuala_Lumpur": "Singapore Standard Time",
    "Asia/Kuwait": "Arab Standard Time",
    "Asia/Bahrain": "Arab Standard Time",
    "Asia/Qatar": "Arab Standard Time",
    "Asia/Muscat": "Arabian Standard Time",
    "Africa/Addis_Ababa": "E. Africa Standard Time",
    "Africa/Asmara": "E. Africa Standard Time",
    "Africa/Dar_es_Salaam": "E. Africa Standard Time",
    "Africa/Djibouti": "E. Africa Standard Time",
    "Africa/Kampala": "E. Africa Standard Time",
    "Africa/Mogadishu": "E. Africa Standard Time",
    "Africa/Accra": "Greenwich Standard Time",
    "Africa/Bamako": "Greenwich Standard Time",
    "Africa/Banjul": "Greenwich Standard Time",
    "Africa/Conakry": "Greenwich Standard Time",
    "Africa/Dakar": "Greenwich Standard Time",
    "Africa/Freetown": "Greenwich Standard Time",
    "Africa/Lome": "Greenwich Standard Time",
    "Africa/Monrovia": "Greenwich Standard Time",
    "Africa/Nouakchott": "Greenwich Standard Time",
    "Africa/Ouagadougou": "Greenwich Standard Time",
    "Africa/Harare": "South Africa Standard Time",
    "Africa/Blantyre": "South Africa Standard Time",
    "Africa/Gaborone": "South Africa Standard Time",
    "Africa/Lusaka": "South Africa Standard Time",
    "Africa/Maputo": "South Africa Standard Time",
    "Africa/Maseru": "South Africa Standard Time",
    "Africa/Mbabane": "South Africa Standard Time",
    "Africa/Kigali": "South Africa Standard Time",
    "Africa/Tunis": "W. Central Africa Standard Time",
    "Africa/Luanda": "W. Central Africa Standard Time",
    "Africa/Kinshasa": "W. Central Africa Standard Time",
    "Africa/El_Aaiun": "Morocco Standard Time",
    "Pacific/Johnston": "Hawaiian Standard Time",
    "Pacific/Rarotonga": "Hawaiian Standard Time",
    "Pacific/Tahiti": "Hawaiian Standard Time",
    "Pacific/Midway": "UTC-11",
    "Pacific/Pago_Pago": "UTC-11",
    "Pacific/Niue": "UTC-11",
    "Pacific/Fakaofo": "UTC+13",
    "Antarctica/McMurdo": "New Zealand Standard Time",
    # tzdata 旧别名（backward 链接）：语义与对应 Windows 官方名完全一致才收录
    "EST5EDT": "Eastern Standard Time",
    "CST6CDT": "Central Standard Time",
    "MST7MDT": "Mountain Standard Time",
    "PST8PDT": "Pacific Standard Time",
    "JST-9": "Tokyo Standard Time",
    "Hongkong": "China Standard Time",
    "Japan": "Tokyo Standard Time",
    "Korea": "Korea Standard Time",
    "ROK": "Korea Standard Time",
    "W-SU": "Russian Standard Time",
    "Eire": "GMT Standard Time",
    "GB": "GMT Standard Time",
    "GB-Eire": "GMT Standard Time",
    "WET": "GMT Standard Time",
    "Portugal": "GMT Standard Time",
    "Greenwich": "GMT Standard Time",
    "Iceland": "Greenwich Standard Time",
    "Iran": "Iran Standard Time",
    "Israel": "Israel Standard Time",
    "Cuba": "Cuba Standard Time",
    "Egypt": "Egypt Standard Time",
    "Libya": "Libya Standard Time",
    "Turkey": "Turkey Standard Time",
    "Poland": "Central European Standard Time",
    "Jamaica": "SA Pacific Standard Time",
    "Navajo": "US Mountain Standard Time",
    "Singapore": "Singapore Standard Time",
    "Zulu": "UTC",
    "Universal": "UTC",
    "UCT": "UTC",
    "UTC0": "UTC",
    "GMT0": "UTC",
})

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
    elif tz_str in LEGACY_WINDOWS_TZ_MAP:
        tz_str = LEGACY_WINDOWS_TZ_MAP[tz_str]
    if ZoneInfo:
        try:
            return ZoneInfo(tz_str)
        except Exception:
            pass
    if tz_str not in _warned_tz:
        _warned_tz.add(tz_str)
        print(t("warn_unknown_tz", tz=tz_str), file=sys.stderr)
    return timezone.utc


def _mk_tz(tz_name):
    """把探测到的时区名变成 (tzinfo, 传给 Graph 的时区名)；解析不了返回 None。

    输入可能是 Windows 名或 IANA 名：Windows 名先查表映射成 IANA 名再交给
    ZoneInfo；传给 Graph 的名字优先用 Windows 官方名（兼容性最稳）。

    :param tz_name: 候选时区名
    :return: (tzinfo, Graph 时区名) 或 None
    """
    if not tz_name:
        return None
    iana = WINDOWS_TZ_MAP.get(tz_name) or LEGACY_WINDOWS_TZ_MAP.get(tz_name, tz_name)
    if ZoneInfo:
        try:
            zi = ZoneInfo(iana)
        except Exception:
            zi = None
        if zi is not None:
            return zi, IANA_TO_WINDOWS.get(iana, iana)
    return None


_POSIX_TZ = object()  # 哨兵：TZ 是解析不了的 POSIX 规则串（CST-8/EST5EDT 等）


def _tz_from_env():
    """从 TZ 环境变量取时区（POSIX 约定，跨平台最直接，优先级最高）。

    值三种情况：IANA/Windows 名直接可用；UTC 类归一成 UTC；解析不了的
    POSIX 规则串（CST-8、EST5EDT、GMT0 等）返回哨兵 _POSIX_TZ——
    TZ 一旦被设置就是权威配置，此时不能再读系统文件（文件可能是另一套时区），
    应直接按运行时偏移兜底。

    :return: (tzinfo, Graph 时区名) 或 None 或 _POSIX_TZ
    """
    env = os.environ.get("TZ", "").strip()
    if not env:
        return None
    if env.upper() in ("UTC", "GMT", "ETC/UTC", "ETC/GMT"):
        return timezone.utc, "UTC"
    r = _mk_tz(env)
    return r if r is not None else _POSIX_TZ


def _tz_from_winreg():
    """从 Windows 注册表 TimeZoneKeyName 取时区名（Windows 专用，其余平台静默跳过）。

    :return: (tzinfo, Graph 时区名) 或 None
    """
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                           r"SYSTEM\CurrentControlSet\Control\TimeZoneInformation")
        tz_name, _ = winreg.QueryValueEx(k, "TimeZoneKeyName")
        winreg.CloseKey(k)
        return _mk_tz(tz_name)
    except Exception:
        return None


def _tz_from_system_tzinfo():
    """从系统 tzinfo 的 .key 取时区名。

    Windows 的 tzinfo 自带注册表名（.key 非 None）；Linux/macOS 只有固定偏移
    （.key 为 None），这条路径自然跳过。

    :return: (tzinfo, Graph 时区名) 或 None
    """
    return _mk_tz(getattr(datetime.now().astimezone().tzinfo, "key", None))


def _tz_from_etc_timezone():
    """读 /etc/timezone（Debian/Ubuntu 专有，其他系统 OSError 跳过）。

    :return: (tzinfo, Graph 时区名) 或 None
    """
    try:
        with open("/etc/timezone") as f:
            name = f.read().strip()
            if name and not name.startswith("#"):
                return _mk_tz(name)
    except OSError:
        pass
    return None


def _tz_from_localtime_link():
    """从 /etc/localtime 符号链接解析 IANA 名（Linux/macOS 通用）。

    :return: (tzinfo, Graph 时区名) 或 None
    """
    try:
        link = os.path.realpath("/etc/localtime")
        marker = "/zoneinfo/"
        if marker in link:
            return _mk_tz(link.split(marker, 1)[1])
    except OSError:
        pass
    return None


def _tz_from_localtime_content():
    """把 /etc/localtime 内容与 tzdata 逐个比对，反推出 IANA 名。

    兜 /etc/localtime 是拷贝而不是符号链接的系统（部分容器/发行版）。
    只在前面的探测全部失败时调用；按文件大小先筛一遍，代价约几十毫秒。

    :return: (tzinfo, Graph 时区名) 或 None
    """
    try:
        with open("/etc/localtime", "rb") as f:
            data = f.read()
    except OSError:
        return None
    if not data:
        return None
    try:
        import zoneinfo as _zi
        roots, names = _zi.TZPATH, _zi.available_timezones()
    except Exception:
        return None
    for name in names:
        # 跳过无法当 Graph 时区名的条目：posix/right 变体、顶层链接（Factory 等
        # 解析出来是 UTC 但名字 Graph 不认）、过时别名（GB-Eire 这类无斜杠的）
        if ("/" not in name or name.startswith(("posix/", "right/"))
                or name in ("localtime", "posixrules", "Factory")):
            continue
        for root in roots:
            try:
                with open(os.path.join(root, name), "rb") as f:
                    if len(data) == os.fstat(f.fileno()).st_size and f.read() == data:
                        return _mk_tz(name)
            except OSError:
                continue
    return None


def _tz_from_offset(now=None):
    """按系统当前偏移推导 Etc/GMT±N 时区（最后的兜底）。

    Etc/GMT 符号与 UTC 偏移相反（UTC+8 = Etc/GMT-8），名字在 Graph 官方支持
    列表里。代价是没有夏令时信息——DST 地区一年里有一半时间会差一小时，
    所以这里警告一次并建议设置 TZ 环境变量。整小时偏移才可用，其余返回 None。

    :param now: 可注入的"当前时间"对象（测试用，默认 datetime.now()）
    :return: (tzinfo, Graph 时区名) 或 None
    """
    off = (now or datetime.now()).astimezone().utcoffset()
    if off is None:
        return None
    secs = int(off.total_seconds())
    if secs % 3600 != 0:
        return None  # 印度/尼泊尔这类半小时偏移没有 Etc 名字，交给最终兜底
    hours = secs // 3600
    if hours == 0:
        return timezone.utc, "UTC"
    name = f"Etc/GMT{'-' if hours > 0 else '+'}{abs(hours)}"
    r = _mk_tz(name)
    if r is not None:
        if name not in _warned_tz:
            _warned_tz.add(name)
            print(t("warn_offset_tz", name=name), file=sys.stderr)
        return r
    # ZoneInfo 也没有（如没装 tzdata 的 Windows）：用固定偏移 tzinfo，名字仍给 Etc/GMT±N
    return timezone(timedelta(seconds=secs)), name


def _detect_local_tz():
    """探测本机时区，返回 (tzinfo, 传给 Graph 的时区名)。

    探测顺序：TZ 环境变量（POSIX 规则串时直接按运行时偏移兜底，
    因为 TZ 一旦设置就是权威配置，不能再读 /etc 下的另一套配置）
    → Windows 注册表 → 系统 tzinfo 的 key → /etc/timezone
    → /etc/localtime 符号链接 → /etc/localtime 内容比对
    → 当前偏移推导 Etc/GMT±N → UTC。
    前一级成功即返回；全部失败时的兜底是固定偏移 + 显式警告，
    绝不再把 naive 本地时间静默标成 UTC（那会让新建日程整体偏移）。

    :return: (tzinfo, 时区名)
    """
    env_r = _tz_from_env()
    if env_r is _POSIX_TZ:
        # TZ 是 POSIX 规则串（如 CST-8）：它是权威配置但解析不出名字，
        # 直接按运行时偏移兜底，绝不回读 /etc 下的另一套时区配置
        r = _tz_from_offset()
        if r is not None:
            return r
        print(t("warn_tz_utc"), file=sys.stderr)
        return datetime.now().astimezone().tzinfo, "UTC"
    if env_r is not None:
        return env_r
    for probe in (_tz_from_winreg, _tz_from_system_tzinfo,
                  _tz_from_etc_timezone, _tz_from_localtime_link,
                  _tz_from_localtime_content, _tz_from_offset):
        r = probe()
        if r is not None:
            return r
    print(t("warn_tz_utc"), file=sys.stderr)
    return datetime.now().astimezone().tzinfo, "UTC"


LOCAL_TZ, LOCAL_TZ_NAME = _detect_local_tz()


def _normalize_dt(s):
    """把 Graph 时间字符串修成 datetime.fromisoformat 能吃的格式。

    Graph 的时间戳可能带 7 位小数，Python 3.11 之前只认 6 位，这里截断；
    结尾的 Z 换成 +00:00。截断时必须保留时区后缀（+08:00/Z），
    否则带偏移的时间会被当成 naive 时间重新解释，时间直接偏移。

    :param s: Graph 的 dateTime 字符串
    :return: 归一化后的字符串
    """
    s = s.replace("Z", "+00:00")
    if "." in s:
        head, rest = s.split(".", 1)
        i = 0
        while i < len(rest) and rest[i].isdigit():
            i += 1
        frac, suffix = rest[:i][:6], rest[i:]
        s = f"{head}.{frac}{suffix}" if frac else f"{head}{suffix}"
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


def _local_time_exists(dt, tz=None):
    """墙钟时间在指定时区是否真实存在（夏令时跳变时如 02:30 这类时间不存在）。

    判定用 roundtrip：naive 时间套上 tz → 转 UTC → 转回 tz，
    回不到原值说明该时刻被折叠/跳过（不存在）。歧义时间（回拨日 01:30）
    fold=0 自洽，不告警——两个时刻都合法，只是选择第一个。

    :param dt: naive datetime
    :param tz: 时区（默认本机 LOCAL_TZ；测试可注入夏令时地区）
    :return: True 存在；False 不存在（跳变被跳过的时间）
    """
    tz = tz or LOCAL_TZ
    try:
        aware = dt.replace(tzinfo=tz)
        return aware.astimezone(timezone.utc).astimezone(tz) == aware
    except Exception:
        return True


# ── 相对时间词（今天/明天/本周X…）──
# 换算基准是运行时刻的系统时钟（now 可注入供测试）："今天"这类词由命令解析
# 而不是 agent 凭上下文推算，从根上杜绝"创建到昨天"这类事故。

_CN_WEEKDAY = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}
_EN_WEEKDAY = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
               "friday": 4, "saturday": 5, "sunday": 6}
_CN_TIME_RE = re.compile(r"(凌晨|早上|上午|中午|下午|晚上)?(\d{1,2})点(半)?$")


def _resolve_relative_date(w, now):
    """把相对日期词解析成 date；不认识返回 None。

    :param w: 今天/明天/后天/本周X/这周X/下周X/today/this friday/next friday…
    :param now: 基准时刻（系统时钟）
    :return: date 或 None
    """
    if w in ("今天", "今日", "today"):
        return now.date()
    if w in ("明天", "明日", "tomorrow"):
        return now.date() + timedelta(days=1)
    if w in ("后天", "後天", "day after tomorrow"):
        return now.date() + timedelta(days=2)
    low = w.lower()
    for prefix, offset in (("本周", 0), ("这周", 0), ("下周", 7)):
        if w.startswith(prefix):
            idx = _CN_WEEKDAY.get(w[len(prefix):].replace("星期", "").replace("礼拜", "").replace("周", ""))
            if idx is not None:
                # 周一起始：本周一 = 今天 - weekday
                return now.date() - timedelta(days=now.weekday()) + timedelta(days=offset + idx)
            return None
    for prefix, offset in (("this ", 0), ("next ", 7)):
        if low.startswith(prefix):
            idx = _EN_WEEKDAY.get(low[len(prefix):])
            if idx is not None:
                return now.date() - timedelta(days=now.weekday()) + timedelta(days=offset + idx)
            return None
    return None


def _relative_dt(s, now=None):
    """把相对时间词（可带时刻）解析成 naive datetime；不认识返回 None。

    支持：今天/明天/后天/今日/明日、本周X/这周X/下周X、today/tomorrow/
    day after tomorrow、this X/next X；时刻可用 24 小时制（"今天 14:00"）
    或中文（"今天下午2点"、"明天上午9点半"）。

    :param s: 相对时间输入
    :param now: 基准时刻，默认系统当前时间
    :return: naive datetime 或 None
    """
    # 基准用 LOCAL_TZ 而不是裸 datetime.now()：与显示/查询窗口共用同一时区基准，
    # 避免系统墙钟与探测链结果不一致时"今天"差一天的极端情况
    now = now or datetime.now(LOCAL_TZ)
    s = s.strip()
    # 1) 整串直接是日期词（今天 / day after tomorrow）
    day = _resolve_relative_date(s, now)
    date_part, minutes = s, None
    if day is None:
        # 2) "日期词 HH:MM"（今天 14:00）
        if " " in s:
            head, tail = s.rsplit(" ", 1)
            try:
                t = datetime.strptime(tail, "%H:%M")
            except ValueError:
                return None
            date_part, minutes = head, t.hour * 60 + t.minute
        else:
            # 3) 中文时刻后缀（今天下午2点 / 明天上午9点半）
            m = _CN_TIME_RE.search(s)
            if m:
                per, hh, half = m.group(1), int(m.group(2)), m.group(3)
                if per in ("下午", "晚上"):
                    hh = hh if hh == 12 else hh + 12
                if per in ("晚上", "凌晨") and hh == 12:
                    hh = 0  # 晚上12点/凌晨12点 = 当天 0 点
                minutes = hh * 60 + (30 if half else 0)
                if minutes >= 1440:
                    return None
                date_part = s[:m.start()]
        day = _resolve_relative_date(date_part, now)
        if day is None:
            return None
    if minutes is None:
        return datetime.combine(day, datetime.min.time())
    return datetime.combine(day, datetime.min.time()) + timedelta(minutes=minutes)


def _parse_dt_arg(s, *, date_only=False, now=None):
    """解析命令行给的时间参数；格式不对抛 CalError（友好提示，不甩 traceback）。

    标准格式："2026-08-10" 或 "2026-08-10 09:00"；
    也支持相对时间词（今天/明天/本周五/今天下午2点…），按运行时刻系统时钟换算。

    :param s: 命令行时间
    :param date_only: True 时只收日期，不收时间
    :param now: 基准时刻（测试注入用，默认系统当前时间）
    :return: naive datetime
    :raises CalError: 时间格式无法解析
    """
    if not s:
        raise CalError(t("err_time_empty"))
    if date_only:
        try:
            return datetime.strptime(s, "%Y-%m-%d")
        except ValueError:
            pass
        rel = _relative_dt(s, now)
        if rel is not None and rel.time() == datetime.min.time():
            return rel
        raise CalError(t("err_time_date", s=s))
    if " " in s:
        try:
            return datetime.strptime(s, "%Y-%m-%d %H:%M")
        except ValueError:
            pass
        rel = _relative_dt(s, now)
        if rel is not None:
            return rel
        raise CalError(t("err_time_dt", s=s))
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        pass
    rel = _relative_dt(s, now)
    if rel is not None:
        return rel
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
