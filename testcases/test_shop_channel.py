# -*- coding: utf-8 -*-
"""店铺与渠道模块用例。"""
import pytest

import config
from common import assert_all, queries
from common.assertions import assert_not_null, assert_response_time


@pytest.mark.shop
@pytest.mark.smoke
def test_SHOP_001_query_shop(client):
    """SHOP-001 查询店铺基础信息（名称、版本、默认国家）。"""
    resp = client.query(queries.SHOP)
    assert_all(resp, "shop")
    assert_not_null(resp.get("shop.name"), "shop.name")
    assert_not_null(resp.get("shop.version"), "shop.version")
    assert_not_null(resp.get("shop.defaultCountry.code"), "shop.defaultCountry.code")


@pytest.mark.shop
def test_SHOP_002_query_channels(client):
    """SHOP-002 查询渠道列表（本环境需鉴权，实证需 AUTHENTICATED_STAFF_USER）。"""
    resp = client.query(queries.CHANNELS)
    assert_all(resp, "channels")
    channels = resp.get("channels") or []
    assert len(channels) > 0, "渠道列表不应为空"


@pytest.mark.shop
def test_SHOP_003_channel_configured_exists(client):
    """SHOP-003 .env 配置的默认渠道必须存在且启用。"""
    resp = client.query(queries.CHANNELS)
    assert_all(resp, "channels")
    channels = resp.get("channels") or []
    matched = [c for c in channels if c.get("slug") == config.CHANNEL]
    assert matched, "配置渠道 %s 不存在，现有：%s" % (
        config.CHANNEL,
        [c.get("slug") for c in channels],
    )
    assert matched[0].get("isActive") is True, "配置渠道 %s 未启用" % config.CHANNEL


@pytest.mark.shop
def test_SHOP_004_channel_fields_complete(client):
    """SHOP-004 渠道返回字段完整（slug/name/currencyCode）。"""
    resp = client.query(queries.CHANNELS)
    assert_all(resp, "channels")
    for ch in resp.get("channels") or []:
        assert_not_null(ch.get("slug"), "channel.slug")
        assert_not_null(ch.get("name"), "channel.name")
        assert_not_null(ch.get("currencyCode"), "channel.currencyCode")


@pytest.mark.shop
def test_SHOP_005_query_response_time(client):
    """SHOP-005 店铺查询响应时间在阈值内。"""
    resp = client.query(queries.SHOP)
    assert_response_time(resp)