"""ocal_i18n 的测试。

被测模块负责多语言，三个职责：
- resolve_lang / set_lang / get_lang：语言解析，优先级是
  --lang 参数 > OCAL_LANG 环境变量 > 系统语言检测
- T 字符串表 + t()：zh/en 两套文案，支持 {name} 占位符填充
- d_md / weekday / join 等格式化函数：语言相关的日期、星期、连接符

两个重点值得所有开发者知道：字符串表完整性是协议级底线——脚本里每处
t() 调用用的键，zh/en 两张表都必须有，缺一个就回退成中文甚至显示键名；
语言相关格式化必须在调用时读当前语言（语言在模块导入后才确定），不能做成常量。
"""
import os
import re
from datetime import date
from pathlib import Path

import pytest

from conftest import SCRIPTS_DIR
from ocal_i18n import t, T, set_lang, get_lang, resolve_lang, d_md, d_ymd, weekday, \
    date_weekday, all_day, join, range_sep, weekday_names, idx_name, imp_name


class TestKeyCompleteness:
    """字符串表完整性，协议级检查。

    遍历 scripts/ 下所有 .py，把 t("...") 用到的键全部收集起来，
    逐一确认 zh 和 en 两张表都有。这条测试是 i18n 的底线：
    漏翻译在 CI 里立刻暴露，而不是等用户在某台机器上看到键名。
    """

    def test_all_keys_in_both_tables(self):
        """扫一遍所有脚本，t() 用到的键在两张表里都不能缺。"""
        used = set()
        for fn in os.listdir(SCRIPTS_DIR):
            if not fn.endswith(".py"):
                continue
            src = (SCRIPTS_DIR / fn).read_text(encoding="utf-8")
            used |= set(re.findall(r'(?<![A-Za-z0-9_])t\(["\']([a-z0-9_]+)["\']', src))
        assert used, "没扫到任何 t() 调用？"
        for key in sorted(used):
            assert key in T["zh"], f"zh 表缺键: {key}"
            assert key in T["en"], f"en 表缺键: {key}"


class TestLangResolution:
    """语言解析 resolve_lang / set_lang / get_lang。

    优先级是 --lang 参数 > OCAL_LANG 环境变量 > 系统语言检测，
    传入不支持的取值会被忽略、落到下一级。这是整个多语言机制的入口。
    """

    def test_override_beats_env(self, monkeypatch):
        """--lang 显式值压过环境变量。"""
        monkeypatch.setenv("OCAL_LANG", "en")
        assert resolve_lang("zh") == "zh"

    def test_env_used_when_no_override(self, monkeypatch):
        """没有显式值时环境变量生效。"""
        monkeypatch.setenv("OCAL_LANG", "en")
        assert resolve_lang(None) == "en"

    def test_os_detection_fallback(self, monkeypatch):
        """环境变量也没设时走系统检测，这里 mock 成中文系统。"""
        monkeypatch.delenv("OCAL_LANG", raising=False)
        monkeypatch.setattr("ocal_i18n._detect_os_lang", lambda: "zh")
        assert resolve_lang(None) == "zh"

    def test_invalid_value_ignored(self, monkeypatch):
        """不支持的取值（fr）被忽略，不会硬套，落到系统检测。"""
        monkeypatch.setenv("OCAL_LANG", "fr")
        monkeypatch.setattr("ocal_i18n._detect_os_lang", lambda: "en")
        assert resolve_lang(None) == "en"

    def test_set_get_roundtrip(self):
        """set_lang 和 get_lang 往返一致。"""
        set_lang("en")
        assert get_lang() == "en"
        set_lang("zh")
        assert get_lang() == "zh"


class TestT:
    """查表函数 t()。

    按当前语言取文案，支持 {name} 占位符填充。
    缺键时的回退链是：当前语言缺 → 中文，中文也缺 → 键名本身，
    键名出现在用户输出里就是漏翻的显性信号。
    """

    def test_lookup_both_languages(self):
        """同一个键在两种语言下取到各自的文案。"""
        set_lang("zh")
        assert t("all_day") == "全天"
        set_lang("en")
        assert t("all_day") == "All day"

    def test_format_args(self):
        """占位符按命名参数填充。"""
        assert t("rec_every_n_days", n=3) == "每3天"

    def test_missing_key_falls_back_zh(self):
        """en 表缺键时回退到中文文案。"""
        T["zh"]["_test_only_key"] = "测试值"
        try:
            set_lang("en")
            assert t("_test_only_key") == "测试值"
        finally:
            del T["zh"]["_test_only_key"]

    def test_missing_everywhere_returns_key(self):
        """两张表都缺时返回键名本身，方便开发期发现漏翻。"""
        assert t("_不存在_的键") == "_不存在_的键"


class TestFormatters:
    """语言相关的日期/星期/连接符格式化。

    d_md / d_ymd / weekday / date_weekday / all_day / join / range_sep /
    weekday_names / idx_name / imp_name 是显示层的常用件，
    列表、详情、定期描述、空闲时段全都依赖它们。
    这些函数在调用时读当前语言，测试里先 set_lang 再断言。
    """

    @pytest.mark.parametrize("lang,expected", [("zh", "08月10日"), ("en", "08/10")])
    def test_d_md(self, lang, expected):
        """短日期：zh 用 08月10日，en 用 08/10。"""
        set_lang(lang)
        assert d_md(date(2026, 8, 10)) == expected

    @pytest.mark.parametrize("lang,expected", [("zh", "2026年08月10日"), ("en", "2026-08-10")])
    def test_d_ymd(self, lang, expected):
        """带年份的日期：read 详情页用。"""
        set_lang(lang)
        assert d_ymd(date(2026, 8, 10)) == expected

    @pytest.mark.parametrize("lang,expected", [("zh", "周一"), ("en", "Mon")])
    def test_weekday(self, lang, expected):
        """星期短名：周一 / Mon。"""
        set_lang(lang)
        assert weekday(date(2026, 8, 10)) == expected

    @pytest.mark.parametrize("lang,expected", [
        ("zh", "08月10日 周一"),
        ("en", "08/10 Mon"),
        ("zh", "2026年08月10日 周一"),   # with_year 分支
    ])
    def test_date_weekday(self, lang, expected):
        """日期加星期的组合串，含带年份的分支，列表分组的公共口径。"""
        set_lang(lang)
        with_year = "年" in expected or expected.startswith("2026")
        assert date_weekday(date(2026, 8, 10), with_year=with_year) == expected

    @pytest.mark.parametrize("lang,expected", [("zh", "全天"), ("en", "All day")])
    def test_all_day(self, lang, expected):
        """全天/All day 的当前语言写法。"""
        set_lang(lang)
        assert all_day() == expected

    @pytest.mark.parametrize("lang,expected", [("zh", "a、b"), ("en", "a, b")])
    def test_join(self, lang, expected):
        """列表连接符：zh 用顿号，en 用逗号，空闲时段列表用句号"""
        set_lang(lang)
        assert join(["a", "b"]) == expected

    @pytest.mark.parametrize("lang,expected", [("zh", "~"), ("en", "-")])
    def test_range_sep(self, lang, expected):
        """日期范围连接符：~ / -，全天跨天显示用。"""
        set_lang(lang)
        assert range_sep() == expected

    @pytest.mark.parametrize("lang,first", [("zh", "周一"), ("en", "Monday")])
    def test_weekday_names(self, lang, first):
        """一周七天名称，周一起，和 Python weekday() 对齐，定期规则格式化用。"""
        set_lang(lang)
        names = weekday_names()
        assert len(names) == 7
        assert names[0] == first

    @pytest.mark.parametrize("lang,expected", [("zh", "第一"), ("en", "first")])
    def test_idx_name(self, lang, expected):
        """序数词翻译：每月第几个周几的规则描述用。"""
        set_lang(lang)
        assert idx_name("first") == expected

    @pytest.mark.parametrize("lang,expected", [("zh", "低"), ("en", "low")])
    def test_imp_name(self, lang, expected):
        """重要度显示值：zh 时 low/high 显示成 低/高。"""
        set_lang(lang)
        assert imp_name("low") == expected
