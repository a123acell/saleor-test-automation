# -*- coding: utf-8 -*-
"""商品列表分页边界用例（Relay Cursor 规范）。

断言目标经 scripts/probe 实证（本地 Saleor 3.23 实例）：
- first=5 正常返回，pageInfo.endCursor / hasNextPage 完整，且末边 cursor 与 endCursor 一致
- 全量翻页：累计边数 == totalCount，无重复（不重不漏）
- first=100（恰好等于上限）正常返回
- first=1000 超上限 -> 顶层错误「exceeds the `first` limit of 100 records」+ data 为 null
- first=0 被视为未提供 -> 顶层错误「must provide a `first` or `last` value」+ data 为 null
- 非法 after cursor -> 顶层错误「Received cursor is invalid.」+ data 为 null
"""
import pytest

from common import queries
from common.assertions import assert_all

PAGE_SIZE = 7


def _fetch_page(anon_client, channel_slug, first, after=None):
    """请求一页商品（products 为公开接口，无需鉴权）。"""
    return anon_client.query(
        queries.PRODUCTS_PAGINATED,
        {"channel": channel_slug, "first": first, "after": after},
        use_auth=False,
    )


@pytest.mark.product
@pytest.mark.smoke
def test_PAGINATION_001_first_page_shape(anon_client, channel_slug):
    """PAGINATION-001 first=5 首页：边数等于 first，pageInfo 字段完整且自洽。"""
    resp = _fetch_page(anon_client, channel_slug, 5)
    assert_all(resp, "products")
    total = resp.get("products.totalCount")
    assert total >= 10, "分页用例前提：环境商品数应多于单页（实际 %s）" % total

    edges = resp.get("products.edges") or []
    assert len(edges) == 5, "first=5 时边数应为 5，实际 %d" % len(edges)
    assert len({e["node"]["id"] for e in edges}) == 5, "首页内商品不应重复"

    info = resp.get("products.pageInfo")
    assert info is not None, "pageInfo 字段不应缺失"
    assert info.get("hasNextPage") is True, "totalCount > first 时应有下一页"
    assert info.get("endCursor"), "hasNextPage=True 时 endCursor 不应为空"
    # Relay 规范：末边的 cursor 与 pageInfo.endCursor 一致
    assert edges[-1]["cursor"] == info["endCursor"], "末边 cursor 应等于 pageInfo.endCursor"


@pytest.mark.product
def test_PAGINATION_002_full_walk_no_duplicate_no_loss(anon_client, channel_slug):
    """PAGINATION-002 按 first=7 全量翻页：累计边数 == totalCount 且无重复。"""
    total = _fetch_page(anon_client, channel_slug, 1).get("products.totalCount")
    assert total >= 10, "分页用例前提：环境商品数应多于单页（实际 %s）" % total

    seen, pages, after = [], 0, None
    while True:
        page = _fetch_page(anon_client, channel_slug, PAGE_SIZE, after)
        assert_all(page, "products")
        edges = page.get("products.edges") or []
        assert len(edges) <= PAGE_SIZE, "单页边数不应超过 first=%d" % PAGE_SIZE
        seen.extend(e["node"]["id"] for e in edges)
        pages += 1

        info = page.get("products.pageInfo") or {}
        if not info.get("hasNextPage"):
            break
        after = info.get("endCursor")
        assert after, "hasNextPage=True 时 endCursor 不应为空"
        assert pages <= 100, "翻页超过 100 次仍未结束，疑似 cursor 循环"

    assert len(seen) == total, "翻页累计 %d 条应等于 totalCount %d" % (len(seen), total)
    assert len(set(seen)) == len(seen), "翻页结果存在重复商品"
    if total:
        assert pages == -(-total // PAGE_SIZE), (
            "页数 %d 应等于 ceil(totalCount/first)=%d" % (pages, -(-total // PAGE_SIZE))
        )


@pytest.mark.product
def test_PAGINATION_003_first_at_limit_100(anon_client, channel_slug):
    """PAGINATION-003 first=100（恰好等于上限）：正常返回，一次取全。"""
    resp = _fetch_page(anon_client, channel_slug, 100)
    assert_all(resp, "products")
    total = resp.get("products.totalCount")
    assert total <= 100, "用例前提：环境商品数不超过 first 上限（实际 %s）" % total

    edges = resp.get("products.edges") or []
    assert len(edges) == total, "first=100 时边数应等于 totalCount %s，实际 %d" % (total, len(edges))
    assert resp.get("products.pageInfo.hasNextPage") is False, "一次取全后不应有下一页"


@pytest.mark.product
@pytest.mark.negative
def test_PAGINATION_004_first_exceeds_limit(anon_client, channel_slug):
    """PAGINATION-004 first=1000 超出上限，返回明确错误且不给数据。"""
    resp = _fetch_page(anon_client, channel_slug, 1000)
    assert resp.status_code == 200
    assert resp.has_errors, "first 超过 100 应返回错误"
    msg = " ".join(resp.error_messages())
    assert "limit of 100" in msg, "错误信息应说明 first 上限，实际 %s" % msg
    assert resp.get("products") is None, "被拒的请求不应返回数据"


@pytest.mark.product
@pytest.mark.negative
def test_PAGINATION_005_first_zero_rejected(anon_client, channel_slug):
    """PAGINATION-005 first=0 被视为未提供分页参数，返回明确错误。"""
    resp = _fetch_page(anon_client, channel_slug, 0)
    assert resp.status_code == 200
    assert resp.has_errors, "first=0 应被视为未提供分页参数而报错"
    msg = " ".join(resp.error_messages())
    assert "first" in msg and "last" in msg, (
        "错误信息应提示必须提供 first/last，实际 %s" % msg
    )
    assert resp.get("products") is None, "报错时不应返回数据"


@pytest.mark.product
@pytest.mark.negative
def test_PAGINATION_006_invalid_cursor_rejected(anon_client, channel_slug):
    """PAGINATION-006 非法 after cursor，返回明确错误且不给数据。"""
    resp = _fetch_page(anon_client, channel_slug, 5, after="garbage-cursor")
    assert resp.status_code == 200
    assert resp.has_errors, "非法 cursor 应返回错误"
    msg = " ".join(resp.error_messages())
    assert "cursor" in msg.lower(), "错误信息应提示 cursor 非法，实际 %s" % msg
    assert resp.get("products") is None, "报错时不应返回数据"
