# -*- coding: utf-8 -*-
"""账户与客户模块用例。

断言目标经 scripts/probe 实证：
- 缺 redirectUrl -> REQUIRED（field=redirectUrl）
- 注册成功 -> requiresConfirmation=True
- 重复邮箱注册 -> 不报错、不暴露「邮箱已存在」（防枚举）
"""
import time

import pytest

import config
from common import assert_all, assert_biz_error, queries
from common.assertions import assert_no_graphql_errors


def _unique_email() -> str:
    return "autotest%d@example.com" % int(time.time() * 1000)


@pytest.mark.account
@pytest.mark.negative
def test_ACCOUNT_001_register_requires_redirect_url(anon_client, channel_slug):
    """ACCOUNT-001 注册缺 redirectUrl，返回 REQUIRED（field=redirectUrl）。"""
    resp = anon_client.mutate(
        queries.ACCOUNT_REGISTER,
        {"input": {"email": _unique_email(), "password": "Test@12345", "channel": channel_slug}},
        use_auth=False,
    )
    assert_no_graphql_errors(resp)
    assert_biz_error(resp, "accountRegister", code="REQUIRED", field="redirectUrl")


@pytest.mark.account
@pytest.mark.smoke
def test_ACCOUNT_002_register_success(anon_client, channel_slug):
    """ACCOUNT-002 带 redirectUrl 注册成功，需邮件确认。"""
    email = _unique_email()
    resp = anon_client.mutate(
        queries.ACCOUNT_REGISTER,
        {
            "input": {
                "email": email,
                "password": "Test@12345",
                "redirectUrl": "http://localhost:3000/confirm",
                "channel": channel_slug,
            }
        },
        use_auth=False,
    )
    assert_all(resp, "accountRegister")
    assert resp.get("accountRegister.user.email") == email
    assert resp.get("accountRegister.requiresConfirmation") is True, "注册后应需要邮件确认"


@pytest.mark.account
def test_ACCOUNT_003_duplicate_register_not_disclosed(anon_client, channel_slug):
    """ACCOUNT-003 重复邮箱注册不报错，不泄露邮箱是否已注册（防枚举）。"""
    email = _unique_email()
    payload = {
        "input": {
            "email": email,
            "password": "Test@12345",
            "redirectUrl": "http://localhost:3000/confirm",
            "channel": channel_slug,
        }
    }
    first = anon_client.mutate(queries.ACCOUNT_REGISTER, payload, use_auth=False)
    assert_all(first, "accountRegister")

    second = anon_client.mutate(queries.ACCOUNT_REGISTER, payload, use_auth=False)
    assert_no_graphql_errors(second)
    assert second.payload_errors("accountRegister") == [], (
        "重复注册不应返回业务错误（避免邮箱枚举），实际 %s"
        % second.payload_error_messages("accountRegister")
    )


@pytest.mark.account
def test_ACCOUNT_004_me_returns_current_user(client):
    """ACCOUNT-004 me 查询返回当前登录管理员。"""
    resp = client.query(queries.ME)
    assert_all(resp, "me")
    assert resp.get("me.email") == config.ADMIN_EMAIL
    assert resp.get("me.isStaff") is True


@pytest.mark.account
def test_ACCOUNT_005_customers_list(client):
    """ACCOUNT-005 查询客户列表，返回总数。"""
    resp = client.query(queries.CUSTOMERS, {"first": 5})
    assert_all(resp, "customers")
    assert resp.get("customers.totalCount") is not None
    edges = resp.get("customers.edges") or []
    assert len(edges) <= 5, "分页参数 first=5 未被遵守"