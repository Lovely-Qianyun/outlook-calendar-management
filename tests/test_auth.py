"""ocal_auth 的测试。

被测模块负责认证状态管理：
- get_token 读 token 文件：没过期直接用，过期了用 refresh token 续期
- _refresh_token 调 msal 换新 token，并把结果写回文件

msal 是假的（通过 sys.modules 注入 _FakeMSAL），token 文件用 tmp_path
指到临时目录，测试不碰真实认证、不碰真实文件。
"""
import json
import sys
import time

import pytest

import ocal_auth as auth
from ocal_errors import CalError


@pytest.fixture
def token_path(tmp_path, monkeypatch):
    """把 token 文件路径指到临时目录，测试互不污染。"""
    p = tmp_path / "token.json"
    monkeypatch.setattr(auth, "TOKEN_PATH", str(p))
    return p


def _write_token(p, **fields):
    """写入一份"正常"的 token 文件，字段可按需覆盖。"""
    data = {"access_token": "acc", "expires_at": time.time() + 3600,
            "refresh_token": "ref", "client_id": "cid", "_authority": "consumers"}
    data.update(fields)
    p.write_text(json.dumps(data), encoding="utf-8")


class TestGetToken:
    """get_token 的分支。

    五个分支：没认证过、token 没过期、过期走续期、
    过期但没有 refresh token、文件损坏。
    """

    def test_no_file_returns_none(self, token_path):
        """还没认证过（没有 token 文件）返回 None。

        上层看到 None 会提示用户先跑 outlook_setup.py。
        """
        assert auth.get_token() is None

    def test_valid_token_returned(self, token_path):
        """没过期的 token 直接返回，不触发续期。

        有效期留 300 秒余量：剩不到 5 分钟也算过期，提前续。
        """
        _write_token(token_path)
        assert auth.get_token() == "acc"

    def test_expired_refreshes(self, token_path, monkeypatch):
        """过期后走续期，refresh token 和应用 ID 透传正确，返回新 token。"""
        _write_token(token_path, expires_at=time.time() - 100)
        seen = {}
        def fake_refresh(refresh, client_id, authority):
            seen["refresh"] = refresh
            seen["client_id"] = client_id
            return "new_acc"
        monkeypatch.setattr(auth, "_refresh_token", fake_refresh)
        assert auth.get_token() == "new_acc"
        assert seen == {"refresh": "ref", "client_id": "cid"}

    def test_missing_refresh_token_raises(self, token_path):
        """过期且没有 refresh token 时给友好报错，提示重新认证。"""
        _write_token(token_path, refresh_token=None, expires_at=time.time() - 100)
        with pytest.raises(CalError):
            auth.get_token()

    def test_corrupt_file_raises(self, token_path):
        """token 文件内容损坏时给友好报错，而不是 traceback。"""
        token_path.write_text("{{{ 不是json", encoding="utf-8")
        with pytest.raises(CalError):
            auth.get_token()


class _FakeMSAL:
    """假的 msal 模块。

    通过 sys.modules 注入后，`from msal import PublicClientApplication`
    会拿到这个类；acquire_token_by_refresh_token 固定返回预设结果，
    测试里改 result 属性来模拟不同分支。
    """
    result = {"access_token": "new_acc", "refresh_token": "new_ref", "expires_in": 3600}

    class PublicClientApplication:
        def __init__(self, *a, **k):
            pass

        def acquire_token_by_refresh_token(self, refresh_token, scopes=None):
            return _FakeMSAL.result


class TestRefreshToken:
    """_refresh_token 的分支。

    四个分支：续期成功并写回文件、refresh token 失效、其他错误、缺 msal 库。
    """

    def test_success_writes_back(self, token_path, monkeypatch):
        """续期成功：返回新 token，并把新值写回文件。

        写回的内容包括 client_id 和 authority——下次续期要靠它们，
        不存的话用户得重新认证。
        """
        monkeypatch.setitem(sys.modules, "msal", _FakeMSAL)
        tok = auth._refresh_token("ref", "cid", "consumers")
        assert tok == "new_acc"
        saved = json.loads(token_path.read_text(encoding="utf-8"))
        assert saved["access_token"] == "new_acc"
        assert saved["refresh_token"] == "new_ref"
        assert saved["client_id"] == "cid"
        assert saved["_authority"] == "consumers"

    def test_invalid_grant_raises(self, token_path, monkeypatch):
        """refresh token 失效（invalid_grant）时给"重新认证"的提示。"""
        _FakeMSAL.result = {"error": "invalid_grant", "error_description": "revoked"}
        monkeypatch.setitem(sys.modules, "msal", _FakeMSAL)
        with pytest.raises(CalError) as ei:
            auth._refresh_token("ref", "cid", "consumers")
        assert "过期" in str(ei.value)

    def test_other_error_with_description(self, token_path, monkeypatch):
        """其他错误带上服务端错误描述，方便排查。"""
        _FakeMSAL.result = {"error": "unknown", "error_description": "something odd"}
        monkeypatch.setitem(sys.modules, "msal", _FakeMSAL)
        with pytest.raises(CalError) as ei:
            auth._refresh_token("ref", "cid", "consumers")
        assert "something odd" in str(ei.value)

    def test_missing_msal_raises(self, token_path, monkeypatch):
        """缺 msal 库时给安装提示。

        正常不会发生（依赖自检会先装），但防御一下总有好处。
        """
        monkeypatch.setitem(sys.modules, "msal", None)
        with pytest.raises(CalError) as ei:
            auth._refresh_token("ref", "cid", "consumers")
        assert "msal" in str(ei.value)
