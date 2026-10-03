# -*- coding: utf-8 -*-
"""订单模块页面对象：列表、筛选面板、详情。"""
from uitests.pages.base import BasePage, DataGridPage


class OrderListPage(DataGridPage):
    PATH = "/dashboard/orders"

    FILTERS_BUTTON = "[data-test-id=filters-button]"
    FILTERS_PANEL = "[data-test-id=filters-panel]"
    ADD_FILTER = "[data-test-id=add-filter-button]"
    RESET_FILTERS = "[data-test-id=reset-all-filters-button]"
    SAVE_FILTERS = "[data-test-id=save-filters-button]"

    def open_filters(self):
        """打开筛选面板并返回面板 Locator。"""
        self.dismiss_announcement()
        self.page.click(self.FILTERS_BUTTON)
        self.page.wait_for_selector(self.FILTERS_PANEL)
        return self.page.locator(self.FILTERS_PANEL)


class OrderDetailPage(BasePage):
    DETAIL_URL_RE = r"/dashboard/orders/(.+)$"

    def wait_loaded(self, timeout_ms: int = 15000):
        self.page.wait_for_function(
            "re => new RegExp(re).test(location.pathname)", arg=self.DETAIL_URL_RE, timeout=timeout_ms
        )
        self.wait_for_header(timeout_ms)