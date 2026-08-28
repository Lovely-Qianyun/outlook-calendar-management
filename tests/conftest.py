"""pytest 公共配置：让脚本目录可导入、语言状态不泄漏、时区固定。"""
import os
import sys
from pathlib import Path

# 固定测试时区为 Asia/Shanghai：多个测试用例按 UTC+8 写死期望值
# （事件用 China Standard Time，换算后与本地窗口比较）。CI runner 是 UTC，
# 不固定的话这些断言会随运行环境时区变化而失败。
# ocal_time 的探测链第一优先读 TZ 环境变量，Windows 上同样生效。
os.environ["TZ"] = "Asia/Shanghai"
try:
    import time as _time
    _time.tzset()
except AttributeError:
    pass  # Windows 无 tzset，探测链读 TZ 环境变量同样生效

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from ocal_i18n import set_lang


@pytest.fixture(autouse=True)
def _lang_reset():
    """每个用例跑完把语言复位到 zh，防止用例之间互相污染。"""
    set_lang("zh")
    yield
    set_lang("zh")


@pytest.fixture
def zh():
    """切到中文输出。"""
    set_lang("zh")
    yield


@pytest.fixture
def en():
    """切到英文输出。"""
    set_lang("en")
    yield
