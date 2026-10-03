# -*- coding: utf-8 -*-
"""已登录的 Dashboard 外壳：侧边导航、用户菜单、登出。"""
from uitests.pages.base import MENU_LIST, BasePage


class DashboardShell(BasePage):
    USER_MENU = "[data-test-id=userMenu]"
    LOGOUT_BUTTON = "[data-test-id=log-out-button]"

    def is_logged_in(self) -> bool:
        return self.page.locator(MENU_LIST).count() == 1

    def nav(self, key: str):
        """点击侧边栏菜单项；key 为 data-test-id 后缀，如 products / orders / configure。"""
        self.dismiss_announcement()
        self.page.click("[data-test-id=menu-item-label-%s]" % key)

    def logout(self):
        self.dismiss_announcement()
        self.page.click(self.USER_MENU)
        self.page.wait_for_selector(self.LOGOUT_BUTTON)
        self.page.click(self.LOGOUT_BUTTON)