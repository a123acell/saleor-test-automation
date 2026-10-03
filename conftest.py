# -*- coding: utf-8 -*-
"""全局 fixture。

分层原则：
- session 级：登录客户端、渠道、首个可用变体 —— 全流程只取一次，避免重复请求
- function 级：购物车 —— 每条用例独立，用例结束自动删除，防止数据残留
- module 级：已完成订单 —— 构造成本高，同模块内复用
"""
import pytest

import config
from common import GraphQLClient, queries
from common.flows import (
    DEFAULT_ADDRESS,
    build_order,
    create_checkout,
    get_first_variant,
    pick_channel,
)


@pytest.fixture(scope="session")
def client() -> GraphQLClient:
    """已登录的管理员客户端（自动携带 Token）。"""
    c = GraphQLClient()
    c.login(config.ADMIN_EMAIL, config.ADMIN_PASSWORD)
    yield c
    c.close()


@pytest.fixture(scope="session")
def anon_client() -> GraphQLClient:
    """未登录客户端，用于鉴权/安全用例。"""
    c = GraphQLClient()
    yield c
    c.close()


@pytest.fixture(scope="session")
def channel_slug(client: GraphQLClient) -> str:
    """默认渠道 slug（取 .env 配置，取不到则回退第一个渠道）。"""
    channels = pick_channel(client, config.CHANNEL) if config.CHANNEL else pick_channel(client)
    return channels["slug"]


@pytest.fixture(scope="session")
def variant(client: GraphQLClient, channel_slug: str) -> dict:
    """首个有定价的商品变体信息（id / 单价 / 所属商品）。"""
    return get_first_variant(client, channel_slug)


@pytest.fixture(scope="session")
def address() -> dict:
    """实测可用的美国收货地址。"""
    return dict(DEFAULT_ADDRESS)


@pytest.fixture
def checkout(client: GraphQLClient, channel_slug: str, variant: dict) -> dict:
    """新建一个含 1 件商品的购物车，用例结束后自动删除。"""
    ck = create_checkout(client, channel_slug, variant["variant_id"], quantity=1)
    yield ck
    try:
        client.mutate(queries.CHECKOUT_DELETE, {"id": ck["id"]})
    except Exception:
        # 清理失败不影响用例结论（购物车过期会由 Saleor 自行回收）
        pass


@pytest.fixture(scope="module")
def completed_order(client: GraphQLClient, channel_slug: str, variant: dict) -> dict:
    """走完整链路生成一个真实订单，供订单模块用例复用。"""
    return build_order(client, channel_slug, variant["variant_id"], quantity=1)