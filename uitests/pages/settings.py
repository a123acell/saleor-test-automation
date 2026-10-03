# -*- coding: utf-8 -*-
"""客户 / 渠道 / 员工 / 站点设置 / 配置中心 页面对象。"""
from uitests.pages.base import BasePage, DataGridPage


class CustomersPage(DataGridPage):
    PATH = "/dashboard/customers/"
    CREATE_CUSTOMER = "[data-test-id=create-customer]"


class ChannelsPage(BasePage):
    """渠道页是普通表格（非 glide 网格），行元素带 data-test-id=channel-row。"""

    PATH = "/dashboard/channels/"
    ROW = "[data-test-id=channel-row]"
    STATUS = "[data-test-id=channel-status]"

    def row_count(self) -> int:
        return self.page.locator(self.ROW).count()

    def first_status(self) -> str:
        return self.page.locator(self.STATUS).first.inner_text().strip()


class StaffPage(DataGridPage):
    PATH = "/dashboard/staff/"
    INVITE = "[data-test-id=invite-staff-member]"


class SiteSettingsPage(BasePage):
    PATH = "/dashboard/site-settings"


class ConfigurationPage(BasePage):
    PATH = "/dashboard/configuration/"
    MENU = "[data-test-id=configuration-menu]"

    def menu_count(self) -> int:
        return self.page.locator(self.MENU + " a").count()