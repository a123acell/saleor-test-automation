# -*- coding: utf-8 -*-
"""UI（Dashboard）自动化 fixture。

设计要点：
- 浏览器 session 级复用；上下文/页面 function 级隔离
- 登录态用 storage_state 复用（整个 session 只登录一次），
  避免 20+ 条用例反复触发 Saleor 的 tokenCreate 限流
- 验证登录/登出本身的用例使用未登录的 page
- 失败自动截图，并保存 Playwright trace 到 ui-artifacts/
- Dashboard 不可达时整组跳过，避免影响纯接口用例的执行
"""
import re
import urllib.request

import pytest
from playwright.sync_api import sync_playwright

import config
from uitests.pages.login import LoginPage
from uitests.pages.shell import DashboardShell

ARTIFACTS = config.UI_ARTIFACTS_DIR
VIEWPORT = {"width": 1440, "height": 900}


def _dashboard_alive() -> bool:
    try:
        urllib.request.urlopen(config.DASHBOARD_URL, timeout=5)
        return True
    except Exception:
        return False


def _artifact_name(nodeid: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", nodeid)


@pytest.fixture(scope="session")
def dashboard_ready():
    if not _dashboard_alive():
        pytest.skip("Dashboard 不可达（%s），跳过 UI 用例" % config.DASHBOARD_URL)


@pytest.fixture(scope="session")
def _playwright():
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def browser(_playwright, dashboard_ready):
    b = _playwright.chromium.launch(headless=not config.UI_HEADED)
    yield b
    b.close()


def _build_context(browser, storage_state=None):
    ctx = browser.new_context(viewport=VIEWPORT, storage_state=storage_state)
    ctx.set_default_timeout(config.UI_TIMEOUT_MS)
    ctx.tracing.start(screenshots=True, snapshots=True)
    return ctx


def _finish_context(ctx, request):
    failed = getattr(request.node, "_ui_failed", False)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    try:
        if failed:
            ctx.tracing.stop(path=str(ARTIFACTS / (_artifact_name(request.node.nodeid) + ".zip")))
        else:
            ctx.tracing.stop()
    finally:
        ctx.close()


@pytest.fixture(scope="session")
def auth_state(browser):
    """登录一次并保存浏览器状态，供全组用例复用。"""
    ctx = browser.new_context(viewport=VIEWPORT)
    page = ctx.new_page()
    login = LoginPage(page, config.DASHBOARD_URL).open()
    login.login(config.ADMIN_EMAIL, config.ADMIN_PASSWORD)
    login.wait_for_dashboard()
    state = ctx.storage_state()
    ctx.close()
    return state


@pytest.fixture
def context(browser, request):
    ctx = _build_context(browser)
    yield ctx
    _finish_context(ctx, request)


@pytest.fixture
def auth_context(browser, auth_state, request):
    ctx = _build_context(browser, storage_state=auth_state)
    yield ctx
    _finish_context(ctx, request)


@pytest.fixture
def page(context):
    """未登录页面：用于登录/鉴权用例。"""
    return context.new_page()


@pytest.fixture
def app(auth_context):
    """已登录页面：用于业务板块用例。"""
    return auth_context.new_page()


@pytest.fixture
def login_page(page):
    return LoginPage(page, config.DASHBOARD_URL).open()


@pytest.fixture
def shell(app):
    """已登录的 Dashboard 外壳，定位在首页。"""
    sh = DashboardShell(app, config.DASHBOARD_URL)
    sh.goto("/dashboard/home")
    return sh


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when == "call" and report.failed:
        item._ui_failed = True
        pg = item.funcargs.get("page") or item.funcargs.get("app")
        if pg is not None:
            try:
                ARTIFACTS.mkdir(parents=True, exist_ok=True)
                pg.screenshot(
                    path=str(ARTIFACTS / (_artifact_name(item.nodeid) + ".png")), full_page=True
                )
            except Exception:
                pass