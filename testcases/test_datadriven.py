# -*- coding: utf-8 -*-
"""数据驱动用例。

query 用例：断言成功（HTTP 200 + 无 GraphQL 错误 + 关键字段非空 + 耗时达标）
error 用例：按 level 断言
  - graphql：顶层 errors 非空（HTTP 可能为 400）
  - payload：无 GraphQL 错误，payload 内业务 errors 非空（可校验错误码/字段）
  - none   ：无任何错误，且目标字段为 null

用例数据来自 data/query_cases.json 与 data/error_cases.json，
新增场景只需改数据文件，无需改代码。
"""
import json

import pytest

import config
from common import queries
from common.assertions import (
    assert_biz_error,
    assert_http_ok,
    assert_no_biz_errors,
    assert_no_graphql_errors,
    assert_not_null,
    assert_response_time,
)
from common.datadriven import build_context, load_cases, resolve_variables
from common.flows import create_checkout

QUERY_CASES = load_cases("query_cases.json")
ERROR_CASES = load_cases("error_cases.json")


@pytest.fixture(scope="module")
def ctx(channel_slug, variant):
    return build_context(
        admin_email=config.ADMIN_EMAIL,
        admin_password=config.ADMIN_PASSWORD,
        channel=channel_slug,
        variant_id=variant["variant_id"],
    )


def _pick_client(auth, client, anon_client):
    return client if auth else anon_client


def _needs_checkout(case) -> bool:
    return "$CHECKOUT_ID" in json.dumps(case.get("variables") or {})


@pytest.mark.datadriven
@pytest.mark.parametrize("case", QUERY_CASES, ids=[c["id"] for c in QUERY_CASES])
def test_datadriven_query_success(case, ctx, client, anon_client):
    """数据驱动：query 成功场景。"""
    gql = getattr(queries, case["query"])
    variables = resolve_variables(case["variables"], ctx)
    active = _pick_client(case["auth"], client, anon_client)

    resp = active.query(gql, variables, use_auth=case["auth"])

    assert_http_ok(resp)
    assert_no_graphql_errors(resp)
    if case.get("operation"):
        assert_no_biz_errors(resp, case["operation"])
    assert_not_null(resp.get(case["expect_data_key"]), case["expect_data_key"])
    for path in case.get("expect_not_null", []):
        assert_not_null(resp.get(path), path)
    assert_response_time(resp)


@pytest.mark.datadriven
@pytest.mark.parametrize("case", ERROR_CASES, ids=[c["id"] for c in ERROR_CASES])
def test_datadriven_error_scenario(case, ctx, client, anon_client, channel_slug, variant):
    """数据驱动：错误 / 空结果场景。"""
    gql = getattr(queries, case["query"])
    variables_ctx = dict(ctx)

    created = None
    if _needs_checkout(case):
        created = create_checkout(client, channel_slug, variant["variant_id"])
        variables_ctx["CHECKOUT_ID"] = created["id"]

    variables = resolve_variables(case["variables"], variables_ctx)
    active = _pick_client(case["auth"], client, anon_client)

    try:
        resp = active.execute(gql, variables, use_auth=case["auth"])
        level = case["level"]

        if level == "graphql":
            assert resp.status_code in (200, 400), "GraphQL 校验错误通常返回 400，实际 %s" % resp.status_code
            assert resp.has_errors, "期望 GraphQL 层错误，实际无错误（%s）" % resp.brief()
        elif level == "payload":
            assert_http_ok(resp)
            assert_no_graphql_errors(resp)
            assert_biz_error(
                resp,
                case["operation"],
                code=case.get("expect_error_code"),
                field=case.get("expect_error_field"),
            )
        elif level == "none":
            assert_http_ok(resp)
            assert_no_graphql_errors(resp)
            assert resp.field(case["operation"]) is None, (
                "期望 %s 返回 null，实际 %r" % (case["operation"], resp.field(case["operation"]))
            )
        else:
            raise AssertionError("未知的 level：%s" % level)
    finally:
        if created:
            client.mutate(queries.CHECKOUT_DELETE, {"id": created["id"]})