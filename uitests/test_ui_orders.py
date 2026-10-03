# -*- coding: utf-8 -*-
"""UI 订单模块用例（UI-ORDER-001 ~ 003）。"""
import pytest

from uitests.pages.orders import OrderDetailPage, OrderListPage

pytestmark = [pytest.mark.ui, pytest.mark.order]


def test_ui_order_001_list_headers(shell):
    """UI-ORDER-001 订单列表：页头 + 表头 + 数据行"""
    page_obj = OrderListPage(shell.page, shell.base_url).open()
    page_obj.wait_for_grid()
    assert page_obj.title == "Orders"
    # 订单表头在宽视口下还会出现 Net / Total，故只校验前导核心列
    assert page_obj.headers()[:5] == [
        "Number",
        "Date",
        "Customer",
        "Payment",
        "Fulfillment status",
    ]
    assert page_obj.row_count() > 0, "订单列表无数据行"


def test_ui_order_002_open_detail_from_row(shell):
    """UI-ORDER-002 单击列表行打开订单详情，页头形如 Order #N"""
    page_obj = OrderListPage(shell.page, shell.base_url).open()
    page_obj.wait_for_grid()

    page_obj.open_row(0)
    detail = OrderDetailPage(shell.page, shell.base_url)
    detail.wait_loaded()

    assert detail.title.startswith("Order #"), "订单详情页头异常：%r" % detail.title
    assert detail.title.replace("Order #", "").isdigit(), "订单详情页头缺少订单号：%r" % detail.title


def test_ui_order_003_filter_panel(shell):
    """UI-ORDER-003 订单筛选面板可打开，且含新增/重置/保存入口"""
    page_obj = OrderListPage(shell.page, shell.base_url).open()
    page_obj.wait_for_grid()

    panel = page_obj.open_filters()
    assert panel.is_visible(), "筛选面板未显示"
    for sel, label in (
        (OrderListPage.ADD_FILTER, "add-filter"),
        (OrderListPage.RESET_FILTERS, "reset-all-filters"),
        (OrderListPage.SAVE_FILTERS, "save-filters"),
    ):
        assert shell.page.locator(sel).count() == 1, "筛选面板缺少 %s 入口" % label