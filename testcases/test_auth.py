# -*- coding: utf-8 -*-
"""鉴权与令牌模块用例。

覆盖：登录成功 / 密码错误 / Token 校验 / Token 刷新。

注意：Saleor 对失败登录有环境级限流（同一用户失败次数越多封禁越久），
因此失败登录统一走 flows.login_expect_failure，被限流时等待解封后重试。
"""
import pytest

import config
from common import assert_all, assert_biz_error, queries
from common.assertions import assert_no_graphql_errors
from common.flows import login_expect_failure


@pytest.mark.auth
@pytest.mark.smoke
def test_AUTH_001_login_success(anon_client):
    """AUTH-001 正确账号密码登录成功，返回可用 Token。"""
    resp = anon_client.mutate(
        queries.TOKEN_CREATE,
        {"email": config.ADMIN_EMAIL, "password": config.ADMIN_PASSWORD},
        use_auth=False,
    )
    assert_all(resp, "tokenCreate")

    token = resp.get("tokenCreate.token")
    assert token, "登录应返回 token"
    assert len(token) > 100, "token 长度异常：%d" % len(token)
    assert resp.get("tokenCreate.refreshToken"), "登录应返回 refreshToken"
    assert resp.get("tokenCreate.user.email") == config.ADMIN_EMAIL
    assert resp.get("tokenCreate.user.isStaff") is True, "管理员账号 isStaff 应为 True"


@pytest.mark.auth
@pytest.mark.negative
def test_AUTH_002_login_wrong_password(anon_client):
    """AUTH-002 密码错误登录失败，返回业务错误且不返回 token。"""
    resp = login_expect_failure(anon_client, config.ADMIN_EMAIL, "definitely-wrong-password")
    assert_no_graphql_errors(resp)
    assert_biz_error(resp, "tokenCreate")
    assert resp.get("tokenCreate.token") is None, "登录失败不应返回 token"


@pytest.mark.auth
@pytest.mark.negative
def test_AUTH_003_login_unknown_email(anon_client):
    """AUTH-003 不存在的邮箱登录失败，返回业务错误。"""
    resp = login_expect_failure(anon_client, "no-such-user@example.com", "whatever")
    assert_no_graphql_errors(resp)
    assert_biz_error(resp, "tokenCreate")
    assert resp.get("tokenCreate.token") is None, "登录失败不应返回 token"


@pytest.mark.auth
def test_AUTH_004_token_verify_valid(anon_client, client):
    """AUTH-004 有效 Token 校验通过（isValid=True）。"""
    resp = anon_client.mutate(queries.TOKEN_VERIFY, {"token": client.token}, use_auth=False)
    assert_all(resp, "tokenVerify")
    assert resp.get("tokenVerify.isValid") is True, "有效 Token 校验应为 True"


@pytest.mark.auth
@pytest.mark.negative
def test_AUTH_005_token_verify_invalid(anon_client):
    """AUTH-005 伪造 Token 校验失败（isValid=False）。"""
    resp = anon_client.mutate(
        queries.TOKEN_VERIFY, {"token": "not-a-real-token"}, use_auth=False
    )
    assert_no_graphql_errors(resp)
    assert resp.get("tokenVerify.isValid") is False, "伪造 Token 校验应为 False"


@pytest.mark.auth
def test_AUTH_006_token_refresh(anon_client, client):
    """AUTH-006 使用 refreshToken 换取新 Token。"""
    # 复用会话级客户端的 refreshToken，避免重复登录触发环境限流
    refresh_token = client.refresh_token
    assert refresh_token, "会话客户端未保存 refreshToken"

    resp = anon_client.mutate(
        queries.TOKEN_REFRESH, {"refreshToken": refresh_token}, use_auth=False
    )
    assert_all(resp, "tokenRefresh")
    assert resp.get("tokenRefresh.token"), "刷新后应返回新 token"