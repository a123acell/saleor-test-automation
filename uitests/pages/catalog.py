# -*- coding: utf-8 -*-
"""商品模块页面对象：列表、创建对话框、详情（含删除）。"""
from uitests.pages.base import BasePage, DataGridPage


class ProductListPage(DataGridPage):
    PATH = "/dashboard/products/"

    SEARCH = "input[placeholder='Search products...']"
    ADD_PRODUCT = "[data-test-id=add-product]"
    PAGINATION_NEXT = "[data-test-id=button-pagination-next]"
    PAGINATION_BACK = "[data-test-id=button-pagination-back]"

    def search(self, keyword: str, timeout_ms: int = 15000):
        """输入关键词并等待搜索结果落定（服务端搜索，存在防抖）。

        等待条件必须是「网格内所有可见行都命中关键词」，不能用「首行命中」：
        初始列表首行商品名本身就含 Reversed，该条件会被搜索前的状态直接满足，
        于是在防抖 + 服务端往返完成前就读到行数，表现为 20 → 20 的假阴性。

        该条件在搜索生效前不可能成立（初始 20 行中只有 1 行命中），
        故能真实反映服务端过滤已完成。要求关键词至少有 1 条命中。
        """
        self.page.fill(self.SEARCH, keyword)
        self.page.wait_for_function(
            "kw => { const rows = Array.from(document.querySelectorAll('table tbody tr'));"
            " return rows.length > 0 && rows.every(r => r.innerText.includes(kw)); }",
            arg=keyword,
            timeout=timeout_ms,
        )

    def open_create_dialog(self) -> "CreateProductDialog":
        self.dismiss_announcement()
        self.page.click(self.ADD_PRODUCT)
        return CreateProductDialog(self.page)


class CreateProductDialog:
    DIALOG = "[data-test-id=create-product-dialog]"
    NAME_INPUT = "[data-test-id=product-name-input]"
    TYPE_COMBO = "[data-test-id=dialog-product-type]"
    SUBMIT = "[data-test-id=submit]"
    OPTION = "[role=option]"

    def __init__(self, page):
        self.page = page
        self.page.wait_for_selector(self.DIALOG)

    def fill(self, name: str, type_index: int = 0) -> "CreateProductDialog":
        """填名称并选择产品类型；未选类型时 Create 按钮为禁用态。"""
        self.page.fill(self.NAME_INPUT, name)
        self.page.click(self.TYPE_COMBO)
        self.page.wait_for_selector(self.OPTION)
        self.page.locator(self.OPTION).nth(type_index).click()
        return self

    def submit(self):
        self.page.locator(self.DIALOG).locator(self.SUBMIT).click()


class ProductDetailPage(BasePage):
    MORE_BUTTON = "[data-test-id=show-more-button]"
    DELETE_ITEM = "[data-test-id=delete-product]"

    DETAIL_URL_RE = r"/dashboard/products/(.+)$"

    def wait_loaded(self, timeout_ms: int = 15000):
        self.page.wait_for_function(
            "re => new RegExp(re).test(location.pathname)", arg=self.DETAIL_URL_RE, timeout=timeout_ms
        )
        self.wait_for_header(timeout_ms)

    def delete(self, expect_gone: str = ""):
        """show-more → Delete product → 确认；完成后回到商品列表。

        expect_gone 传入商品名时，会等到列表中不再出现该商品，确保删除真正落库。
        只等待列表元素出现会产生假阳性：确认弹窗背后的列表 DOM 早已存在，
        测试会提前结束并中断删除请求，导致数据残留。
        """
        self.dismiss_announcement()
        self.page.click(self.MORE_BUTTON)
        self.page.wait_for_selector(self.DELETE_ITEM)
        self.page.click(self.DELETE_ITEM)
        dialog = self.page.locator("[role=dialog], [role=alertdialog]").last
        dialog.wait_for()
        dialog.locator("button:has-text('Delete')").last.click()
        self.page.wait_for_selector(ProductListPage.ADD_PRODUCT)
        if expect_gone:
            self.page.wait_for_function(
                "name => !Array.from(document.querySelectorAll('table tbody tr'))"
                "  .some(r => r.innerText.includes(name))",
                arg=expect_gone,
                timeout=20000,
            )