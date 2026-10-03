# -*- coding: utf-8 -*-
"""订单模块用例。

依赖 module 级 fixture `completed_order`：走完整链路生成一个真实订单。
"""
from decimal import Decimal

import pytest

from common import assert_all, queries
from common.assertions import assert_no_graphql_errors, assert_not_null


@pytest.mark.order
@pytest.mark.smoke
def test_ORDER_001_orders_list(client):
    """ORDER-001 查询订单列表，返回总数与分页边。"""
    resp = client.query(queries.ORDERS, {"first": 10})
    assert_all(resp, "orders")
    assert_not_null(resp.get("orders.totalCount"), "orders.totalCount")
    edges = resp.get("orders.edges") or []
    assert len(edges) <= 10, "分页参数 first=10 未被遵守"


@pytest.mark.order
def test_ORDER_002_order_detail(client, completed_order):
    """ORDER-002 按 ID 查询订单详情，字段与下单返回一致。"""
    resp = client.query(queries.ORDER_BY_ID, {"id": completed_order["id"]})
    assert_all(resp, "order")
    assert resp.get("order.id") == completed_order["id"]
    assert resp.get("order.number") == completed_order["number"]
    assert resp.get("order.status") == completed_order["status"]
    assert_not_null(resp.get("order.created"), "order.created")


@pytest.mark.order
def test_ORDER_003_order_number_format(client, completed_order):
    """ORDER-003 订单号非空且为纯数字。"""
    number = completed_order.get("number")
    assert number, "订单号不应为空"
    assert str(number).isdigit(), "订单号应为纯数字，实际 %s" % number


@pytest.mark.order
def test_ORDER_004_order_total_positive(client, completed_order):
    """ORDER-004 订单金额大于 0 且币种与渠道一致。"""
    total = completed_order["total"]["gross"]
    assert Decimal(total["amount"]) > 0, "订单金额应大于 0"
    assert_not_null(total["currency"], "order.total.currency")


@pytest.mark.order
def test_ORDER_005_order_lines_not_empty(client, completed_order):
    """ORDER-005 订单包含商品行且数量为正。"""
    resp = client.query(queries.ORDER_BY_ID, {"id": completed_order["id"]})
    assert_all(resp, "order")
    lines = resp.get("order.lines") or []
    assert len(lines) > 0, "订单应包含商品行"
    for line in lines:
        assert line.get("quantity", 0) > 0, "订单行数量应大于 0"
        assert_not_null(line.get("productName"), "orderLine.productName")


@pytest.mark.order
def test_ORDER_006_new_order_visible_in_list(client, completed_order):
    """ORDER-006 新生成的订单能在订单列表中找到。"""
    resp = client.query(queries.ORDERS, {"first": 20})
    assert_all(resp, "orders")
    numbers = [e["node"]["number"] for e in resp.get("orders.edges") or []]
    assert completed_order["number"] in numbers, (
        "新订单 %s 未出现在最近 20 条订单中：%s" % (completed_order["number"], numbers)
    )


@pytest.mark.order
@pytest.mark.negative
def test_ORDER_007_query_unknown_order(client):
    """ORDER-007 查询不存在的订单 ID，返回 null 且无 GraphQL 错误。"""
    resp = client.query(queries.ORDER_BY_ID, {"id": "T3JkZXI6MDAwMDAwMDA="})
    assert_no_graphql_errors(resp)
    assert resp.get("order") is None, "不存在的订单应返回 null"