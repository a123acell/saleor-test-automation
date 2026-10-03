# -*- coding: utf-8 -*-
"""UI 写操作闭环用例（UI-WRITE-001 ~ 002）：创建 / 删除商品，含自动清理。"""
import time

import pytest

from uitests.pages.catalog import ProductDetailPage, ProductListPage

pytestmark = [pytest.mark.ui, pytest.mark.product]


def _unique_name(tag: str) -> str:
    """生成当次运行唯一的商品名，避免历史残留干扰断言。"""
    return "UI-AUTO-%s-%d" % (tag, int(time.time() * 1000) % 10_000_000)


def test_ui_write_001_create_product(shell):
    """UI-WRITE-001 创建商品：详情页标题校验 + 列表置顶校验，并清理本次数据"""
    name = _unique_name("CREATE")
    listing = ProductListPage(shell.page, shell.base_url).open()
    listing.wait_for_grid()

    listing.open_create_dialog().fill(name).submit()
    detail = ProductDetailPage(shell.page, shell.base_url)
    detail.wait_loaded()
    assert detail.title == name, "创建后详情页标题不符：%r" % detail.title

    listing = ProductListPage(shell.page, shell.base_url).open()
    listing.wait_for_grid()
    assert listing.count_rows_containing(name) == 1, "新建商品未出现在列表"
    assert listing.first_row_text().startswith(name), "新建商品未置顶（列表按更新时间倒序）"

    # 清理：删除本次创建的商品，避免数据残留
    listing.open_row(0)
    ProductDetailPage(shell.page, shell.base_url).delete(expect_gone=name)


def test_ui_write_002_delete_product(shell):
    """UI-WRITE-002 删除商品：删除后列表不再出现该商品"""
    name = _unique_name("DELETE")
    listing = ProductListPage(shell.page, shell.base_url).open()
    listing.wait_for_grid()

    listing.open_create_dialog().fill(name).submit()
    ProductDetailPage(shell.page, shell.base_url).wait_loaded()

    listing = ProductListPage(shell.page, shell.base_url).open()
    listing.wait_for_grid()
    assert listing.count_rows_containing(name) == 1, "新建商品未出现在列表"

    listing.open_row(0)
    ProductDetailPage(shell.page, shell.base_url).delete(expect_gone=name)

    listing = ProductListPage(shell.page, shell.base_url).open()
    listing.wait_for_grid()
    assert listing.count_rows_containing(name) == 0, "删除后列表仍存在该商品"