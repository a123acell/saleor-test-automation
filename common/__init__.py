# -*- coding: utf-8 -*-
"""公共模块：统一请求层、响应封装、断言、日志、GraphQL 语句。"""
from common import queries
from common.assertions import (
    assert_all,
    assert_biz_error,
    assert_field_equals,
    assert_http_ok,
    assert_keys_present,
    assert_no_biz_errors,
    assert_no_graphql_errors,
    assert_not_null,
    assert_response_time,
)
from common.client import GraphQLClient
from common.logger import get_logger
from common.money import money, money_add, money_equal
from common.response import GraphQLResponse

__all__ = [
    "queries",
    "GraphQLClient",
    "GraphQLResponse",
    "get_logger",
    "money",
    "money_equal",
    "money_add",
    "assert_http_ok",
    "assert_no_graphql_errors",
    "assert_no_biz_errors",
    "assert_biz_error",
    "assert_not_null",
    "assert_field_equals",
    "assert_response_time",
    "assert_keys_present",
    "assert_all",
]