# -*- coding: utf-8 -*-
"""登录页对象。"""
from uitests.pages.base import EMAIL_INPUT, BasePage


class LoginPage(BasePage):
    PATH = "/"

    PASSWORD_INPUT = "input[name=password]"
    SUBMIT = "[data-test-id=submit]"
    FORGOT_LINK = "[data-test-id=reset-password-link]"

    def is_loaded(self) -> bool:
        return self.page.locator(EMAIL_INPUT).count() == 1

    def login(self, email: str, password: str):
        self.page.fill(EMAIL_INPUT, email)
        self.page.fill(self.PASSWORD_INPUT, password)
        self.page.click(self.SUBMIT)

    def wait_for_dashboard(self, timeout_ms: int = 30000):
        self.page.wait_for_url("**/dashboard/**", timeout=timeout_ms)