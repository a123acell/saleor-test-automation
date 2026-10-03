# -*- coding: utf-8 -*-
"""安全用例：未授权访问、Token 篡改、注入字符。

断言目标经 scripts/probe 实证：
- 无 Token 访问管理类接口 -> HTTP 200 + GraphQL 权限错误 + data 为 null
- 篡改签名 -> GraphQL 错误「Signature verification failed」
- 垃圾 Token -> 视为匿名，me 为 null，不抛 500
- 注入字符 -> 安全返回 null，不抛 500
"""
import pytest

from common import queries
from common.assertions import assert_no_graphql_errors


def _assert_no_server_error(resp):
    """任何情况下都不应出现 5xx。"""
    assert resp.status_code < 500, "服务端不应返回 5xx，实际 %s" % resp.status_code


@pytest.mark.security
def test_SEC_001_orders_without_token(anon_client):
    """SEC-001 未携带 Token 访问订单列表，被权限拦截。"""
    resp = anon_client.query(queries.ORDERS, {"first": 1}, use_auth=False)
    _assert_no_server_error(resp)
    assert resp.status_code == 200
    assert resp.has_errors, "未授权访问应返回 GraphQL 权限错误"
    assert "MANAGE_ORDERS" in " ".join(resp.error_messages()), (
        "错误信息应提示所需权限，实际 %s" % resp.error_messages()
    )
    assert resp.get("orders") is None, "未授权时不应返回订单数据"


@pytest.mark.security
def test_SEC_002_customers_without_token(anon_client):
    """SEC-002 未携带 Token 访问客户列表，被权限拦截。"""
    resp = anon_client.query(queries.CUSTOMERS, {"first": 1}, use_auth=False)
    _assert_no_server_error(resp)
    assert resp.has_errors, "未授权访问应返回 GraphQL 权限错误"
    assert resp.get("customers") is None, "未授权时不应返回客户数据"


@pytest.mark.security
def test_SEC_003_me_without_token_returns_null(anon_client):
    """SEC-003 未登录查询 me 返回 null，且不泄露错误细节。"""
    resp = anon_client.query(queries.ME, use_auth=False)
    _assert_no_server_error(resp)
    assert_no_graphql_errors(resp)
    assert resp.get("me") is None, "未登录时 me 应为 null"


@pytest.mark.security
def test_SEC_004_tampered_signature_rejected(anon_client, client):
    """SEC-004 篡改 Token 签名，认证失败。"""
    tampered = client.token[:-5] + "AAAAA"
    resp = anon_client.query(queries.ME, token=tampered, use_auth=False)
    _assert_no_server_error(resp)
    assert resp.has_errors, "篡改签名应导致认证失败"
    assert any(
        "signature" in msg.lower() or "verification" in msg.lower()
        for msg in resp.error_messages()
    ), "应提示签名校验失败，实际 %s" % resp.error_messages()
    assert resp.get("me") is None


@pytest.mark.security
def test_SEC_005_garbage_token_treated_as_anonymous(anon_client):
    """SEC-005 非 JWT 格式的垃圾 Token 被当作匿名，不抛 500。"""
    resp = anon_client.query(queries.ME, token="garbage.token.value", use_auth=False)
    _assert_no_server_error(resp)
    assert_no_graphql_errors(resp)
    assert resp.get("me") is None, "无效 Token 不应获得身份"


@pytest.mark.security
def test_SEC_006_injection_chars_safe(anon_client):
    """SEC-006 注入字符作为查询参数，安全返回 null，不抛 500。"""
    resp = anon_client.query(
        "query($s:String){channel(slug:$s){id slug}}",
        {"s": "default-channel' OR '1'='1"},
        use_auth=False,
    )
    _assert_no_server_error(resp)
    assert_no_graphql_errors(resp)
    assert resp.get("channel") is None, "注入字符不应匹配到任何渠道"


@pytest.mark.security
def test_SEC_007_injection_in_products_search(client, channel_slug):
    """SEC-007 注入字符作为商品搜索词，安全返回空结果，不抛 500。"""
    resp = client.query(
        "query($c:String!,$s:String!){products(first:5,channel:$c,search:$s){totalCount}}",
        {"c": channel_slug, "s": "'; DROP TABLE products; --"},
    )
    _assert_no_server_error(resp)
    assert_no_graphql_errors(resp)
    assert resp.get("products.totalCount") == 0, "注入字符串不应命中任何商品"


@pytest.mark.security
def test_SEC_008_channels_requires_auth(anon_client):
    """SEC-008 未登录访问渠道列表被拦截（本环境渠道接口需鉴权）。"""
    resp = anon_client.query(queries.CHANNELS, use_auth=False)
    _assert_no_server_error(resp)
    assert resp.has_errors, "未授权访问渠道接口应返回 GraphQL 权限错误"
    assert resp.get("channels") is None, "未授权时不应返回渠道数据"