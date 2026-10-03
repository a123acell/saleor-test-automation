# -*- coding: utf-8 -*-
"""商品与目录模块用例。"""
import pytest

from common import assert_all, queries
from common.assertions import assert_no_graphql_errors, assert_not_null


@pytest.mark.product
@pytest.mark.smoke
def test_PRODUCT_001_products_list(client, channel_slug):
    """PRODUCT-001 按渠道查询商品列表，返回总数与分页边。"""
    resp = client.query(queries.PRODUCTS, {"channel": channel_slug, "first": 10})
    assert_all(resp, "products")
    total = resp.get("products.totalCount")
    assert total and total > 0, "商品总数应大于 0，实际 %s" % total
    edges = resp.get("products.edges") or []
    assert len(edges) > 0, "商品列表不应为空"
    assert len(edges) <= 10, "分页参数 first=10 未被遵守，实际返回 %d" % len(edges)


@pytest.mark.product
def test_PRODUCT_002_products_have_variant_pricing(client, channel_slug):
    """PRODUCT-002 商品变体带定价（channel 参数生效）。"""
    resp = client.query(queries.PRODUCTS, {"channel": channel_slug, "first": 5})
    assert_all(resp, "products")
    found = False
    for edge in resp.get("products.edges") or []:
        for variant in (edge.get("node") or {}).get("variants") or []:
            price = ((variant.get("pricing") or {}).get("price") or {}).get("gross")
            if price:
                assert_not_null(price.get("amount"), "variant.price.amount")
                assert_not_null(price.get("currency"), "variant.price.currency")
                found = True
                break
        if found:
            break
    assert found, "前 5 个商品中没有带定价的变体，channel 参数可能未生效"


@pytest.mark.product
def test_PRODUCT_003_product_by_id(client, channel_slug, variant):
    """PRODUCT-003 按 ID 查询单个商品，字段与列表一致。"""
    resp = client.query(
        queries.PRODUCT_BY_ID, {"id": variant["product_id"], "channel": channel_slug}
    )
    assert_all(resp, "product")
    assert resp.get("product.id") == variant["product_id"], "商品 ID 不一致"
    assert resp.get("product.name") == variant["product_name"], "商品名称不一致"
    assert_not_null(resp.get("product.slug"), "product.slug")


@pytest.mark.product
@pytest.mark.negative
def test_PRODUCT_004_product_invalid_id(client, channel_slug):
    """PRODUCT-004 不存在的商品 ID 返回 null，不抛 GraphQL 错误。"""
    resp = client.query(
        queries.PRODUCT_BY_ID,
        {"id": "UHJvZHVjdDoxMjM0NTY3ODk=", "channel": channel_slug},
    )
    assert_no_graphql_errors(resp)
    assert resp.get("product") is None, "不存在的商品应返回 null"


@pytest.mark.product
def test_PRODUCT_005_product_variants(client, channel_slug):
    """PRODUCT-005 查询变体列表，返回带定价的变体。"""
    resp = client.query(queries.PRODUCT_VARIANTS, {"channel": channel_slug, "first": 10})
    assert_all(resp, "productVariants")
    total = resp.get("productVariants.totalCount")
    assert total and total > 0, "变体总数应大于 0"


@pytest.mark.product
def test_PRODUCT_006_categories(client):
    """PRODUCT-006 查询分类列表。"""
    resp = client.query(queries.CATEGORIES, {"first": 10})
    assert_all(resp, "categories")
    assert_not_null(resp.get("categories.totalCount"), "categories.totalCount")


@pytest.mark.product
@pytest.mark.negative
def test_PRODUCT_007_products_missing_required_channel(client):
    """PRODUCT-007 缺少必填 channel 参数，返回 GraphQL 校验错误。"""
    resp = client.query(queries.PRODUCTS, {"first": 5})
    assert resp.has_errors, "缺少必填参数 channel 应返回 GraphQL 错误"
    assert resp.error_codes() or resp.error_messages(), "应给出错误详情"