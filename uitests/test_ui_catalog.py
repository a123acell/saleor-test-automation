# -*- coding: utf-8 -*-
"""UI 商品模块用例（UI-PROD-001 ~ 004）。"""
import pytest

from uitests.pages.catalog import ProductDetailPage, ProductListPage

pytestmark = [pytest.mark.ui, pytest.mark.product]

SEARCH_KEYWORD = "Reversed"


def test_ui_prod_001_search_filters_grid(shell):
    """UI-PROD-001 商品列表搜索：结果收敛、每行命中关键词、且与未过滤命中数交叉一致"""
    page_obj = ProductListPage(shell.page, shell.base_url).open()
    page_obj.wait_for_grid()
    before = page_obj.row_count()
    matched_before = page_obj.count_rows_containing(SEARCH_KEYWORD)

    # 前置条件：未过滤列表中必须存在不命中关键词的行，否则「收敛」无从体现
    assert matched_before < before, (
        "前置条件不成立：未过滤列表 %d 行全部命中 %r，无法验证过滤效果" % (before, SEARCH_KEYWORD)
    )

    page_obj.search(SEARCH_KEYWORD)
    after = page_obj.row_count()

    assert after >= 1, "搜索 %r 无任何命中" % SEARCH_KEYWORD
    assert after < before, "搜索后行数未收敛：%d → %d" % (before, after)
    assert page_obj.count_rows_containing(SEARCH_KEYWORD) == after, "搜索结果中存在未命中关键词的行"
    # 交叉校验：过滤结果数应等于未过滤列表中命中该关键词的行数（两次独立推导）
    assert after == matched_before, (
        "搜索结果数(%d)与未过滤列表命中数(%d)不一致" % (after, matched_before)
    )


def test_ui_prod_002_list_headers(shell):
    """UI-PROD-002 商品列表表头列完整且顺序正确"""
    page_obj = ProductListPage(shell.page, shell.base_url).open()
    page_obj.wait_for_grid()
    # glide-data-grid 按视口宽度虚拟化列，仅校验前导核心列
    assert page_obj.headers()[:6] == [
        "Product",
        "Availability",
        "Price",
        "Category",
        "Type",
        "Last updated",
    ]
    assert page_obj.row_count() >= 1


def test_ui_prod_003_open_detail_from_row(shell):
    """UI-PROD-003 单击列表行打开商品详情，且详情标题与首行商品名一致"""
    page_obj = ProductListPage(shell.page, shell.base_url).open()
    page_obj.wait_for_grid()
    first_row = page_obj.first_row_text()

    page_obj.open_row(0)
    detail = ProductDetailPage(shell.page, shell.base_url)
    detail.wait_loaded()

    assert detail.title, "商品详情页未渲染标题"
    assert first_row.startswith(detail.title), (
        "详情标题(%s)与列表首行(%s)不一致" % (detail.title, first_row[:40])
    )


def test_ui_prod_004_pagination(shell):
    """UI-PROD-004 商品列表分页：翻页后内容变化且仍有数据"""
    page_obj = ProductListPage(shell.page, shell.base_url).open()
    page_obj.wait_for_grid()
    first_before = page_obj.first_row_text()

    next_btn = shell.page.locator(ProductListPage.PAGINATION_NEXT)
    assert next_btn.is_enabled(), "下一页按钮不可用（数据不足一页）"
    next_btn.click()
    page_obj.wait_for_grid()
    shell.page.wait_for_timeout(1200)

    assert page_obj.row_count() > 0, "翻页后无数据行"
    assert page_obj.first_row_text() != first_before, "翻页后首行未变化"