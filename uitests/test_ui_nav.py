# -*- coding: utf-8 -*-
"""UI 五大板块冒烟用例（UI-NAV-001 ~ 005）。"""
import pytest

from uitests.pages.catalog import ProductListPage
from uitests.pages.orders import OrderListPage
from uitests.pages.settings import (
    ChannelsPage,
    ConfigurationPage,
    CustomersPage,
)

pytestmark = [pytest.mark.ui, pytest.mark.ui_smoke]


def test_ui_nav_001_products(shell):
    """UI-NAV-001 商品板块：侧边栏点击导航 + 页头/表头/数据行齐备"""
    shell.nav("products")
    shell.page.wait_for_url("**/dashboard/products/**")
    page_obj = ProductListPage(shell.page, shell.base_url)
    page_obj.dismiss_announcement()
    page_obj.wait_for_grid()
    assert page_obj.title == "Products"
    # glide-data-grid 按视口宽度虚拟化列，仅校验前导核心列，避免视口依赖
    assert page_obj.headers()[:6] == [
        "Product",
        "Availability",
        "Price",
        "Category",
        "Type",
        "Last updated",
    ]
    assert page_obj.row_count() > 0, "商品列表无数据行"


def test_ui_nav_002_orders(shell):
    """UI-NAV-002 订单板块：页头 + 表头 + 数据行"""
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


def test_ui_nav_003_customers(shell):
    """UI-NAV-003 客户板块：页头 + 表头 + 数据行"""
    page_obj = CustomersPage(shell.page, shell.base_url).open()
    page_obj.wait_for_grid()
    assert page_obj.title == "Customers"
    assert page_obj.headers()[:3] == ["Customer name", "Customer e-mail", "No. of orders"]
    assert page_obj.row_count() > 0, "客户列表无数据行"


def test_ui_nav_004_channels(shell):
    """UI-NAV-004 渠道板块：页头 + 渠道行 + 状态列"""
    page_obj = ChannelsPage(shell.page, shell.base_url).open()
    page_obj.wait_for_header()
    assert page_obj.title == "Channels"
    assert page_obj.row_count() >= 1, "渠道列表无数据行"
    assert page_obj.first_status() in {"Active", "Inactive"}, "渠道状态列取值异常"


def test_ui_nav_005_configuration(shell):
    """UI-NAV-005 配置中心：页头 + 配置菜单项"""
    page_obj = ConfigurationPage(shell.page, shell.base_url).open()
    page_obj.wait_for_header()
    assert page_obj.title == "Configuration"
    assert page_obj.menu_count() >= 10, "配置菜单项过少：%d" % page_obj.menu_count()