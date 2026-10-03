# -*- coding: utf-8 -*-
"""UI 页面对象基类与数据表格操作封装。

定位策略全部来自探针实测（03-自己留着看/probe/probe_ui_*.py），不凭记忆猜测：
- 登录表单：input[name=email] / input[name=password] / [data-test-id=submit]
- 侧边导航：[data-test-id=menu-item-label-*]
- 页头标题：[data-test-id=page-header]（首行即标题）
- 列表：无障碍表 table thead th / table tbody tr（文本可读，但元素不可见）
        真实交互面是 canvas，须按几何坐标点击才能打开行详情
- 公告横幅：[data-test-id=ripple-video-announcement-dismiss]（浮层会拦截点击，须先关闭）
"""
from playwright.sync_api import Page

# glide-data-grid 几何常量（实测：表头 41px，行高 40px，首列 x 偏移约 140px）
GRID_HEADER_H = 41
GRID_ROW_H = 40
GRID_FIRST_COL_X = 140

ANNOUNCEMENT_DISMISS = "[data-test-id=ripple-video-announcement-dismiss]"
PAGE_HEADER = "[data-test-id=page-header]"
MENU_LIST = "[data-test-id=menu-list]"
EMAIL_INPUT = "input[name=email]"


class BasePage:
    """页面对象基类：导航、公告关闭、页头读取。"""

    PATH = "/"

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url.rstrip("/")

    def goto(self, path: str):
        self.page.goto(self.base_url + path, wait_until="domcontentloaded")
        self.dismiss_announcement()

    def open(self) -> "BasePage":
        self.goto(self.PATH)
        return self

    def dismiss_announcement(self):
        """关闭 Saleor Pulse 公告横幅；该浮层覆盖页面会拦截后续点击。"""
        btn = self.page.locator(ANNOUNCEMENT_DISMISS)
        if btn.count():
            try:
                btn.first.click(timeout=2500)
                self.page.wait_for_timeout(300)
            except Exception:
                # 横幅可能已自动消失或被其它元素遮挡，忽略即可
                pass

    def wait_for_header(self, timeout_ms: int = 15000):
        self.page.wait_for_selector(PAGE_HEADER, timeout=timeout_ms)

    @property
    def title(self) -> str:
        el = self.page.locator(PAGE_HEADER)
        if not el.count():
            return ""
        return el.first.inner_text().split("\n")[0].strip()

    @property
    def url(self) -> str:
        return self.page.url


class DataGridPage(BasePage):
    """glide-data-grid 列表页：读取表头/行文本，按坐标点击打开行详情。"""

    ROWS = "table tbody tr"
    HEADERS = "table thead th"

    def wait_for_grid(self, min_rows: int = 1, timeout_ms: int = 15000):
        self.page.wait_for_function(
            "n => document.querySelectorAll('table tbody tr').length >= n",
            arg=min_rows,
            timeout=timeout_ms,
        )

    def headers(self):
        return self.page.eval_on_selector_all(
            self.HEADERS, "els => els.map(e => e.innerText.trim()).filter(Boolean)"
        )

    def row_count(self) -> int:
        return self.page.locator(self.ROWS).count()

    def row_text(self, index: int = 0) -> str:
        return self.page.locator(self.ROWS).nth(index).inner_text()

    def first_row_text(self) -> str:
        return self.row_text(0)

    def count_rows_containing(self, keyword: str) -> int:
        texts = self.page.eval_on_selector_all(
            self.ROWS, "els => els.map(e => e.innerText)"
        )
        return sum(1 for t in texts if keyword in t)

    def open_row(self, index: int = 0):
        """glide-data-grid 由 canvas 绘制，无障碍单元格不可点击，需按坐标点击。"""
        box = self.page.locator("canvas").first.bounding_box()
        assert box, "未找到 datagrid canvas，页面可能尚未渲染完成"
        before = self.page.url
        x = box["x"] + GRID_FIRST_COL_X
        y = box["y"] + GRID_HEADER_H + GRID_ROW_H * index + GRID_ROW_H / 2
        self.page.mouse.click(x, y)
        self.page.wait_for_function("prev => location.href !== prev", arg=before, timeout=15000)