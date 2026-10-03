# -*- coding: utf-8 -*-
"""购物车模块用例。

重点验证：金额计算、行操作幂等、异常输入。
"""
import base64

import pytest

from common import assert_all, assert_biz_error, money, money_equal, queries
from common.assertions import assert_no_graphql_errors, assert_not_null


@pytest.mark.cart
@pytest.mark.smoke
def test_CART_001_create_checkout(checkout, variant):
    """CART-001 创建购物车并加购，金额等于单价 × 数量。"""
    assert_not_null(checkout.get("id"), "checkout.id")
    assert_not_null(checkout.get("token"), "checkout.token")
    assert checkout.get("lines"), "购物车应有商品行"

    expected = money(variant["price"]) * 1
    actual = checkout["totalPrice"]["gross"]["amount"]
    assert money_equal(actual, expected), "购物车金额期望 %s，实际 %s" % (expected, actual)
    assert checkout["totalPrice"]["gross"]["currency"] == variant["currency"]


@pytest.mark.cart
def test_CART_002_query_checkout(client, checkout, variant):
    """CART-002 查询购物车详情，行数与商品一致。"""
    resp = client.query(queries.CHECKOUT_QUERY, {"id": checkout["id"]})
    assert_all(resp, "checkout")
    assert resp.get("checkout.id") == checkout["id"]
    assert resp.get("checkout.quantity") == 1, "购物车数量应为 1"
    assert resp.get("checkout.email") == "buyer@example.com"


@pytest.mark.cart
def test_CART_003_lines_add(client, checkout, variant):
    """CART-003 追加商品行，数量与金额同步增长。"""
    resp = client.mutate(
        queries.CHECKOUT_LINES_ADD,
        {"id": checkout["id"], "lines": [{"quantity": 2, "variantId": variant["variant_id"]}]},
    )
    assert_all(resp, "checkoutLinesAdd")
    quantity = resp.get("checkoutLinesAdd.checkout.quantity")
    assert quantity == 3, "追加 2 件后总数量应为 3，实际 %s" % quantity

    expected = money(variant["price"]) * 3
    actual = resp.get("checkoutLinesAdd.checkout.totalPrice.gross.amount")
    assert money_equal(actual, expected), "追加后金额期望 %s，实际 %s" % (expected, actual)


@pytest.mark.cart
def test_CART_004_lines_update(client, checkout, variant):
    """CART-004 更新商品行数量，金额按新数量重算。"""
    line_id = checkout["lines"][0]["id"]
    resp = client.mutate(
        queries.CHECKOUT_LINES_UPDATE,
        {"id": checkout["id"], "lines": [{"lineId": line_id, "quantity": 5}]},
    )
    assert_all(resp, "checkoutLinesUpdate")
    assert resp.get("checkoutLinesUpdate.checkout.quantity") == 5

    expected = money(variant["price"]) * 5
    actual = resp.get("checkoutLinesUpdate.checkout.totalPrice.gross.amount")
    assert money_equal(actual, expected), "更新后金额期望 %s，实际 %s" % (expected, actual)


@pytest.mark.cart
def test_CART_005_line_delete(client, checkout):
    """CART-005 删除商品行后购物车为空。"""
    line_id = checkout["lines"][0]["id"]
    resp = client.mutate(
        queries.CHECKOUT_LINE_DELETE, {"id": checkout["id"], "lineId": line_id}
    )
    assert_all(resp, "checkoutLineDelete")
    lines = resp.get("checkoutLineDelete.checkout.lines") or []
    assert lines == [], "删除后商品行应为空，实际 %s" % lines


@pytest.mark.cart
def test_CART_006_email_update(client, checkout):
    """CART-006 更新购物车邮箱。"""
    new_email = "updated-buyer@example.com"
    resp = client.mutate(
        queries.CHECKOUT_EMAIL_UPDATE, {"id": checkout["id"], "email": new_email}
    )
    assert_all(resp, "checkoutEmailUpdate")
    assert resp.get("checkoutEmailUpdate.checkout.email") == new_email


@pytest.mark.cart
@pytest.mark.negative
def test_CART_007_create_with_invalid_variant(client, channel_slug):
    """CART-007 使用不存在的变体 ID 建购物车，返回业务错误而非 500。"""
    resp = client.mutate(
        queries.CHECKOUT_CREATE,
        {
            "input": {
                "channel": channel_slug,
                "email": "buyer@example.com",
                "lines": [{"quantity": 1, "variantId": "UHJvZHVjdFZhcmlhbnQ6OTk5OTk5"}],
            }
        },
    )
    assert_no_graphql_errors(resp)
    assert_biz_error(resp, "checkoutCreate")


@pytest.mark.cart
@pytest.mark.negative
def test_CART_008_query_unknown_checkout(client):
    """CART-008 查询格式合法但不存在的购物车 ID，返回 null 且无 GraphQL 错误。"""
    # checkout 主键是 UUID，需构造合法 UUID 才能走到「查不到」而非「格式错误」
    fake_id = base64.b64encode(
        b"Checkout:00000000-0000-0000-0000-000000000000"
    ).decode()
    resp = client.query(queries.CHECKOUT_QUERY, {"id": fake_id})
    assert_no_graphql_errors(resp)
    assert resp.get("checkout") is None, "不存在的购物车应返回 null"


@pytest.mark.cart
@pytest.mark.negative
def test_CART_009_query_malformed_checkout_id(client):
    """CART-009 查询格式非法的购物车 ID，返回 GraphQL 错误而非 500。"""
    resp = client.query(queries.CHECKOUT_QUERY, {"id": "Q2hlY2tvdXQ6MDAwMDAwMDA="})
    assert resp.status_code < 500, "不应返回 5xx"
    assert resp.has_errors, "非法 UUID 应返回 GraphQL 错误"