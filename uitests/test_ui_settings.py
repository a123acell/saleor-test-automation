# -*- coding: utf-8 -*-
"""UI 渠道 / 员工 / 站点设置用例（UI-CHAN-001、UI-STAFF-001、UI-SET-001）。"""
import pytest

from uitests.pages.settings import ChannelsPage, SiteSettingsPage, StaffPage

pytestmark = [pytest.mark.ui, pytest.mark.shop]


def test_ui_chan_001_channels_rows(shell):
    """UI-CHAN-001 渠道列表：渠道行齐备且状态列取值合法"""
    page_obj = ChannelsPage(shell.page, shell.base_url).open()
    page_obj.wait_for_header()
    assert page_obj.title == "Channels"
    count = page_obj.row_count()
    assert count >= 1, "渠道列表无渠道行"
    assert page_obj.first_status() in {"Active", "Inactive"}, "渠道状态列取值异常"


def test_ui_staff_001_staff_list(shell):
    """UI-STAFF-001 员工列表：页头 + 表头 + 数据行"""
    page_obj = StaffPage(shell.page, shell.base_url).open()
    page_obj.wait_for_grid()
    assert page_obj.title == "Staff Members"
    assert page_obj.headers()[:4] == ["Name", "Status", "Customer", "Email Address"]
    assert page_obj.row_count() > 0, "员工列表无数据行"


def test_ui_set_001_site_settings(shell):
    """UI-SET-001 站点设置页可打开并渲染 Store 页头"""
    page_obj = SiteSettingsPage(shell.page, shell.base_url).open()
    page_obj.wait_for_header()
    assert page_obj.title == "Store"