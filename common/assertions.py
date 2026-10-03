# -*- coding: utf-8 -*-
"""断言工具。

Saleor 的 HTTP 状态码恒为 200，真正的失败藏在：
- 顶层 `errors`（GraphQL 语法/字段/校验错误）
- payload 内的 `errors` 数组（业务错误，带 code）

因此断言优先判断 **错误码**，不匹配文案（文案会随版本变化）。
"""
from typing import Any, Optional, Sequence

import config
from common.response import GraphQLResponse


def _attach(resp: GraphQLResponse) -> str:
    """构造失败信息时附上请求与响应摘要，便于定位。"""
    return "\n  请求: %s\n  响应: %s" % (
        str(resp.request_body.get("query", "")).strip()[:300],
        resp.brief(),
    )


def assert_http_ok(resp: GraphQLResponse, expected: int = 200) -> None:
    assert resp.status_code == expected, (
        "HTTP 状态码期望 %s，实际 %s%s" % (expected, resp.status_code, _attach(resp))
    )


def assert_no_graphql_errors(resp: GraphQLResponse) -> None:
    """断言顶层无 GraphQL 错误。"""
    assert not resp.has_errors, (
        "存在 GraphQL 错误：%s%s" % ("; ".join(resp.error_messages()), _attach(resp))
    )


def assert_no_biz_errors(resp: GraphQLResponse, operation: str) -> None:
    """断言某操作的业务 errors 为空。"""
    errors = resp.payload_errors(operation)
    assert not errors, (
        "操作 %s 返回业务错误：%s%s"
        % (operation, resp.payload_error_messages(operation), _attach(resp))
    )


def assert_biz_error(
    resp: GraphQLResponse,
    operation: str,
    code: Optional[str] = None,
    field: Optional[str] = None,
) -> None:
    """断言某操作返回业务错误，可进一步校验错误码与字段。"""
    errors = resp.payload_errors(operation)
    assert errors, "操作 %s 期望返回业务错误，实际 errors 为空%s" % (operation, _attach(resp))
    if code is not None:
        codes = resp.payload_error_codes(operation)
        assert code in codes, (
            "操作 %s 期望错误码 %s，实际 %s%s" % (operation, code, codes, _attach(resp))
        )
    if field is not None:
        fields = resp.payload_error_fields(operation)
        assert field in fields, (
            "操作 %s 期望错误字段 %s，实际 %s%s" % (operation, field, fields, _attach(resp))
        )


def assert_not_null(value: Any, name: str) -> None:
    assert value is not None, "%s 不应为空，实际为 None" % name


def assert_field_equals(resp: GraphQLResponse, path: str, expected: Any) -> None:
    actual = resp.get(path)
    assert actual == expected, (
        "字段 %s 期望 %r，实际 %r%s" % (path, expected, actual, _attach(resp))
    )


def assert_response_time(resp: GraphQLResponse, max_ms: Optional[int] = None) -> None:
    """断言单接口响应耗时未超过阈值。"""
    limit = max_ms if max_ms is not None else config.MAX_RESPONSE_MS
    assert resp.elapsed_ms <= limit, (
        "响应耗时 %.0fms 超过阈值 %dms%s" % (resp.elapsed_ms, limit, _attach(resp))
    )


def assert_all(
    resp: GraphQLResponse,
    operation: str,
    max_ms: Optional[int] = None,
    check_time: bool = True,
) -> None:
    """常规成功用例的统一断言：HTTP 200 + 无 GraphQL 错误 + 无业务错误 +（可选）耗时达标。"""
    assert_http_ok(resp)
    assert_no_graphql_errors(resp)
    assert_no_biz_errors(resp, operation)
    if check_time:
        assert_response_time(resp, max_ms)


def assert_keys_present(node: dict, keys: Sequence[str]) -> None:
    """断言字典包含指定键（键存在，值可为 None）。"""
    missing = [k for k in keys if k not in node]
    assert not missing, "缺少字段：%s" % missing