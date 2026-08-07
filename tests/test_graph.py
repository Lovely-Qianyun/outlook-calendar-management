"""ocal_graph 的测试。

被测模块是 Graph API 调用层，测试重点是网络健壮性：
- 429 限流按 Retry-After 头或 1/2/4 秒退避重试
- 500/503 只有 GET/DELETE 重试，POST/PATCH 不重试——重发可能造成重复数据
- 连接错误 GET/DELETE 重试两次、POST/PATCH 直接提示先 list 确认
- 401 和常见 4xx 错误码映射成友好文案

所有请求都是 mock 的，测试本身不发任何真实网络请求。
Resp 是假的响应对象，fake_request fixture 按顺序吐响应并记录调用次数。
"""
import json

import pytest

import ocal_graph as g
from ocal_errors import CalError


class Resp:
    """假的 requests 响应对象。

    状态码、响应头、响应文本或 JSON 载荷都可控；
    json() 优先返回显式给的 payload，否则解析 text。
    """

    def __init__(self, status=200, headers=None, text="", payload=None):
        self.status_code = status
        self.headers = headers or {}
        self.text = text
        self._payload = payload

    def json(self):
        if self._payload is not None:
            return self._payload
        return json.loads(self.text)


@pytest.fixture
def fake_request(monkeypatch):
    """把 requests.request 换成按顺序吐响应的假实现，并记录调用与 sleep。

    给几个响应就允许几次请求，请求次数超了会断言失败——
    这是"恰好重试了 N 次"这类断言的机制。
    raiser 参数可让前几次调用抛网络异常（模拟连接错误/超时）。
    """
    state = {"calls": [], "sleeps": []}

    def install(responses, raiser=None):
        def _req(*a, **k):
            state["calls"].append((a, k))
            if raiser and len(state["calls"]) <= len(raiser):
                raise raiser[len(state["calls"]) - 1]
            return responses[len(state["calls"]) - 1]
        monkeypatch.setattr(g.requests, "request", _req)
        monkeypatch.setattr(g.time, "sleep", lambda s: state["sleeps"].append(s))
        return state
    return install


class TestRetryAfter:
    """Retry-After 头解析 _retry_after_seconds。

    429 限流的等待时间优先用响应头，头缺失或解析不了就回退指数退避，
    所以这两种情况都要返回 None 而不是抛异常。
    """

    def test_valid_seconds(self):
        """正常取值：秒数可以带小数（Graph 实际会返回小数秒）。"""
        r = Resp(status=429, headers={"Retry-After": "3.5"})
        assert g._retry_after_seconds(r) == 3.5

    def test_missing_header(self):
        """没有这个头返回 None，调用方回退指数退避。"""
        assert g._retry_after_seconds(Resp(status=429)) is None

    def test_unparseable(self):
        """头是乱写的也返回 None，不能抛异常。"""
        r = Resp(status=429, headers={"Retry-After": "abc"})
        assert g._retry_after_seconds(r) is None


class TestCall:
    """核心请求 _call 的重试与错误映射。

    逐条验证：429/500/连接错误的次数与等待、POST/PATCH 不重试、
    错误码到友好文案的映射、204 无内容、不可变 ID 请求头。
    """

    def test_single_success(self, fake_request):
        """一次请求直接成功，不多发。"""
        st = fake_request([Resp(payload={"value": []})])
        assert g._call("GET", "/me/events", "tk") == {"value": []}
        assert len(st["calls"]) == 1

    def test_429_retries_then_succeeds(self, fake_request):
        """429 限流重试两次后成功，退避按 1/2/4 秒表取前两档。"""
        st = fake_request([Resp(status=429), Resp(status=429), Resp(payload={"ok": 1})])
        assert g._call("GET", "/me/events", "tk") == {"ok": 1}
        assert len(st["calls"]) == 3
        assert st["sleeps"] == [1, 2]

    def test_429_honors_retry_after(self, fake_request):
        """有 Retry-After 头时按它等，不按退避表。"""
        st = fake_request([Resp(status=429, headers={"Retry-After": "5"}), Resp(payload={})])
        g._call("GET", "/me/events", "tk")
        assert st["sleeps"] == [5]

    def test_500_post_no_retry(self, fake_request):
        """500 对 POST 不重试，直接报错。

        服务端可能已经处理了请求，重发会把同一个日程创建两遍，
        宁可让用户看到错误手动确认。
        """
        st = fake_request([Resp(status=500, text="boom")])
        with pytest.raises(CalError) as ei:
            g._call("POST", "/me/events", "tk", data={})
        assert "API 错误 500" in str(ei.value)
        assert len(st["calls"]) == 1

    def test_500_get_retries_until_exhausted(self, fake_request):
        """500 对 GET 重试到次数耗尽（共 4 次）才报错。"""
        st = fake_request([Resp(status=500, text="x")] * 4)
        with pytest.raises(CalError):
            g._call("GET", "/me/events", "tk")
        assert len(st["calls"]) == 4

    def test_401_login_expired(self, fake_request):
        """401 转成"登录已过期"的友好提示，引导用户重新认证。"""
        fake_request([Resp(status=401, text="unauthorized")])
        with pytest.raises(CalError) as ei:
            g._call("GET", "/me/events", "tk")
        assert "登录已过期" in str(ei.value)

    def test_item_not_found_message(self, fake_request):
        """ErrorItemNotFound 转成"不存在或已删除"的提示。"""
        payload = {"error": {"code": "ErrorItemNotFound", "message": "not found"}}
        fake_request([Resp(status=404, payload=payload)])
        with pytest.raises(CalError) as ei:
            g._call("GET", "/me/events/X", "tk")
        assert "不存在" in str(ei.value)

    def test_crossing_boundary_message(self, fake_request):
        """相邻出现冲突转成调整时间的提示。

        定期系列里把某次改到跨过相邻一次时 Graph 会拒绝，
        这里的文案要告诉用户往哪个方向调。
        """
        payload = {"error": {"code": "ErrorOccurrenceCrossingBoundary", "message": "x"}}
        fake_request([Resp(status=400, payload=payload)])
        with pytest.raises(CalError) as ei:
            g._call("PATCH", "/me/events/X", "tk", data={})
        assert "相邻出现" in str(ei.value)

    def test_204_returns_none(self, fake_request):
        """204 无内容（删除成功）返回 None，调用方不用处理响应体。"""
        fake_request([Resp(status=204)])
        assert g._call("DELETE", "/me/events/X", "tk") is None

    def test_non_json_error_still_reported(self, fake_request):
        """响应体不是 JSON 时也要把原文报出来，方便排查。"""
        fake_request([Resp(status=500, text="oops no json")])
        with pytest.raises(CalError) as ei:
            g._call("POST", "/me/events", "tk", data={})
        assert "oops no json" in str(ei.value)

    def test_network_error_get_retries_then_fails(self, fake_request):
        """连接错误对 GET 重试两次后报网络错误。"""
        exc = g.requests.exceptions.ConnectionError("down")
        st = fake_request([], raiser=[exc, exc, exc])
        with pytest.raises(CalError) as ei:
            g._call("GET", "/me/events", "tk")
        assert "网络错误" in str(ei.value)
        assert len(st["calls"]) == 3

    def test_network_error_post_fails_immediately(self, fake_request):
        """连接错误对 POST 不重试，提示先 list 确认。

        请求可能已经提交（只是没收到响应），盲目重发会造重复日程。
        """
        exc = g.requests.exceptions.Timeout("slow")
        st = fake_request([], raiser=[exc])
        with pytest.raises(CalError) as ei:
            g._call("POST", "/me/events", "tk", data={})
        assert "先 list 确认" in str(ei.value)
        assert len(st["calls"]) == 1

    def test_immutable_id_header(self, fake_request):
        """prefer_immutable 时带上不可变 ID 请求头。

        事件在容器间移动时 ID 会变，这个头保证删除/更新始终指向同一事件。
        """
        st = fake_request([Resp(payload={})])
        g._call("GET", "/me/events", "tk", prefer_immutable=True)
        headers = st["calls"][0][1]["headers"]
        assert headers["Prefer"] == 'IdType="ImmutableId"'


class TestGetAll:
    """翻页 _get_all。

    跟着响应里的 @odata.nextLink 一直翻，把各页的 value 拼成完整列表；
    Graph 单次最多返回 200 条，日程多时必须翻页。
    """

    def test_pagination_collects_all(self, fake_request):
        """两页数据按顺序拼起来。"""
        fake_request([
            Resp(payload={"value": [{"id": 1}], "@odata.nextLink": "https://x/2"}),
            Resp(payload={"value": [{"id": 2}]}),
        ])
        items = g._get_all("/me/events", "tk")
        assert [i["id"] for i in items] == [1, 2]

    def test_single_page(self, fake_request):
        """没有下一页时只取一页。"""
        fake_request([Resp(payload={"value": [{"id": 1}]})])
        assert len(g._get_all("/me/events", "tk")) == 1
