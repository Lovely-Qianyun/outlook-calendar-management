"""pytest 公共配置：让脚本目录可导入、语言状态不泄漏。"""
import sys
from pathlib import Path

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
