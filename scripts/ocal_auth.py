"""ocal_auth — 认证与 token：token 文件读写、自动续期。"""
import os, json, time

from ocal_errors import CalError
from ocal_i18n import t

TOKEN_PATH = os.path.expanduser("~/.outlook_cal_token.json")


def setup_hint():
    """认证引导文案（跟随当前语言）。

    不能做成常量：语言可能在模块导入之后才被设置（--lang 在 main 里才解析）。

    :return: 提示用户怎么跑认证的字符串
    """
    return t("setup_hint")


# ── 认证 ──────────────────────────────────────────

def get_token():
    """拿一个能用的访问令牌：没过期直接返回，过期了用 refresh token 续。

    :return: access token 字符串；还没认证过返回 None
    :raises CalError: token 文件损坏 / 没有 refresh token / 续期失败
    """
    if not os.path.exists(TOKEN_PATH):
        return None
    try:
        with open(TOKEN_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        raise CalError(t("err_token_corrupt", hint=setup_hint()))
    expires_at = data.get('expires_at', 0)
    access_token = data.get('access_token')
    if access_token and expires_at and expires_at > time.time() + 300:
        return access_token
    refresh_token = data.get('refresh_token')
    if not refresh_token:
        raise CalError(t("err_no_refresh", hint=setup_hint()))
    client_id = data.get('client_id') or os.environ.get('OUTLOOK_CLIENT_ID', '')
    if not client_id:
        raise CalError(t("err_no_client_id", hint=setup_hint()))
    return _refresh_token(refresh_token, client_id, data.get('_authority', 'consumers'))


def _refresh_token(refresh_token, client_id, authority):
    """用 refresh token 换新的 access token，并把结果写回 token 文件。

    :param refresh_token: 上次存下来的 refresh token
    :param client_id: 应用 ID（续期必须和认证时一致）
    :param authority: 账户类型（consumers 或 common）
    :return: 新的 access token
    :raises CalError: 缺 msal 库 / refresh token 失效 / 其他刷新失败
    """
    try:
        from msal import PublicClientApplication
    except ImportError:
        raise CalError(t("err_no_msal"))
    app = PublicClientApplication(client_id, authority=f"https://login.microsoftonline.com/{authority}")
    result = app.acquire_token_by_refresh_token(refresh_token, scopes=["Calendars.ReadWrite"])
    if 'access_token' in result:
        result['refresh_token'] = result.get('refresh_token', refresh_token)
        result['expires_at'] = time.time() + result.get('expires_in', 3600)
        result['_authority'] = authority
        result['client_id'] = client_id
        with open(TOKEN_PATH, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False)
        return result['access_token']
    error = result.get('error', 'unknown')
    desc = result.get('error_description', '')
    if error == 'invalid_grant':
        raise CalError(t("err_refresh_invalid"))
    raise CalError(t("err_refresh_fail", error=error, desc=desc[:200]))
