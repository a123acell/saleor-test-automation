# -*- coding: utf-8 -*-
"""UI 鉴权与访问控制用例（UI-AUTH-001 ~ 005）。"""
import config
import pytest

from uitests.pages.base import EMAIL_INPUT, MENU_LIST
from uitests.pages.login import LoginPage
from uitests.pages.shell import DashboardShell

pytestmark = [pytest.mark.ui, pytest.mark.auth]


def _is_token_create(response) -> bool:
    """登录请求：POST 到 GraphQL 且报文体包含 tokenCreate。

    page.expect_response 的回调收到的是 Response，需经 .request 取请求侧信息。
    """
    request = response.request
    return (
        request.method == "POST"
        and "graphql" in request.url
        and "tokenCreate" in (request.post_data or "")
    )


@pytest.mark.ui_smoke
def test_ui_auth_001_login_page_elements(login_page):
    """UI-AUTH-001 登录页关键元素完整（邮箱 / 密码 / 提交 / 忘记密码）"""
    assert login_page.is_loaded(), "登录页未渲染邮箱输入框"
    assert login_page.page.locator(LoginPage.PASSWORD_INPUT).count() == 1
    assert login_page.page.locator(LoginPage.SUBMIT).count() >= 1
    assert login_page.page.locator(LoginPage.FORGOT_LINK).count() == 1
    body = login_page.page.inner_text("body")
    assert "Sign In" in body and "Forgot password?" in body


@pytest.mark.ui_smoke
def test_ui_auth_002_login_success(page):
    """UI-AUTH-002 正确账号登录成功并跳转 Dashboard"""
    login = LoginPage(page, config.DASHBOARD_URL).open()
    login.login(config.ADMIN_EMAIL, config.ADMIN_PASSWORD)
    login.wait_for_dashboard()
    assert "/dashboard/" in page.url, "登录后 URL 未进入 Dashboard：%s" % page.url
    assert DashboardShell(page, config.DASHBOARD_URL).is_logged_in(), "登录后未渲染侧边导航"


def test_ui_auth_003_login_wrong_password(page):
    """UI-AUTH-003 错误密码登录失败：服务端拒绝凭证且停留在登录页

    不能只靠固定 sleep 后断言「URL 未进入 Dashboard」——登录请求尚未返回时该断言
    恒成立，会掩盖「错误密码其实登录成功」的缺陷。这里改为等 tokenCreate 请求返回，
    并从响应体确认凭证被拒绝（技术信号，不依赖前端文案）。
    """
    login = LoginPage(page, config.DASHBOARD_URL).open()
    with page.expect_response(_is_token_create, timeout=15000) as info:
        login.login(config.ADMIN_EMAIL, "wrong-password-for-ui-test")

    payload = info.value.json()
    token_create = (payload.get("data") or {}).get("tokenCreate") or {}
    errors = payload.get("errors") or token_create.get("errors")
    assert errors, "错误密码的登录响应未返回鉴权错误：%s" % payload

    # 给 SPA 留出处理响应的时间，使「未进入 Dashboard」的断言不是空断言
    page.wait_for_timeout(1500)
    assert "/dashboard/" not in page.url, "错误密码竟进入 Dashboard：%s" % page.url
    assert login.is_loaded(), "错误密码提交后登录表单消失"
    assert page.locator(MENU_LIST).count() == 0, "未登录却渲染了侧边导航"


def test_ui_auth_004_guard_unauthenticated(page):
    """UI-AUTH-004 未登录访问受保护页 → 渲染登录表单而非业务内容

    改为等待登录表单渲染（真实信号）；若受保护页被放行、渲染了业务内容，
    此处会超时失败，而不是靠固定 sleep 后得到一个恒真的断言。
    """
    page.goto(config.DASHBOARD_URL + "/dashboard/products/", wait_until="domcontentloaded")
    page.wait_for_selector(EMAIL_INPUT, timeout=15000)
    assert page.locator(EMAIL_INPUT).count() == 1, "未登录访问受保护页未出现登录表单"
    assert page.locator(MENU_LIST).count() == 0, "未登录却渲染了侧边导航"


def test_ui_auth_005_logout(app):
    """UI-AUTH-005 登出后回到未登录状态"""
    shell = DashboardShell(app, config.DASHBOARD_URL)
    shell.goto("/dashboard/home")
    assert shell.is_logged_in(), "登出前未处于登录态"
    shell.logout()
    app.wait_for_selector(EMAIL_INPUT, timeout=15000)
    assert app.locator(EMAIL_INPUT).count() == 1, "登出后未回到登录页"
    assert app.locator(MENU_LIST).count() == 0, "登出后侧边导航仍在"