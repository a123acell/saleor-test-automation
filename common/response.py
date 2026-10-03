# -*- coding: utf-8 -*-
"""GraphQL 响应封装。

把一次 HTTP 响应拆成三层，便于分层断言：

1. 传输层：HTTP 状态码、耗时（毫秒）
2. GraphQL 层：顶层 errors（语法错误、字段不存在、校验失败）
3. 业务层：payload 内的 errors 数组（如 checkoutCreate.errors）

Saleor 的约定是 HTTP 恒为 200，业务失败通过第 2、3 层体现，
所以断言不能只看状态码。
"""
from typing import Any, Dict, List, Optional


class GraphQLResponse:
    """一次 GraphQL 请求的完整结果。"""

    def __init__(
        self,
        status_code: int,
        payload: Optional[Dict[str, Any]],
        elapsed_ms: float,
        request_body: Optional[Dict[str, Any]] = None,
        raw_text: str = "",
    ):
        self.status_code = status_code
        self.payload = payload if isinstance(payload, dict) else {}
        self.elapsed_ms = elapsed_ms
        self.request_body = request_body or {}
        self.raw_text = raw_text

    # ---------- GraphQL 层 ----------

    @property
    def data(self) -> Optional[Dict[str, Any]]:
        return self.payload.get("data")

    @property
    def errors(self) -> List[Dict[str, Any]]:
        """顶层 errors：GraphQL 传输/语法层错误。"""
        return self.payload.get("errors") or []

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)

    def error_messages(self) -> List[str]:
        return [e.get("message", "") for e in self.errors]

    def error_codes(self) -> List[str]:
        codes = []
        for e in self.errors:
            ext = e.get("extensions") or {}
            if ext.get("code"):
                codes.append(ext["code"])
        return codes

    # ---------- 业务层 ----------

    def field(self, operation: str) -> Optional[Dict[str, Any]]:
        """取 data 下某个操作的返回对象，如 field('checkoutCreate')。"""
        if not self.data:
            return None
        return self.data.get(operation)

    def payload_errors(self, operation: str) -> List[Dict[str, Any]]:
        """取某操作 payload 内的业务 errors 数组。"""
        node = self.field(operation)
        if isinstance(node, dict):
            return node.get("errors") or []
        return []

    def payload_error_codes(self, operation: str) -> List[Optional[str]]:
        return [e.get("code") for e in self.payload_errors(operation)]

    def payload_error_fields(self, operation: str) -> List[Optional[str]]:
        return [e.get("field") for e in self.payload_errors(operation)]

    def payload_error_messages(self, operation: str) -> List[str]:
        return [e.get("message", "") for e in self.payload_errors(operation)]

    # ---------- 取值 ----------

    def get(self, path: str, default: Any = None) -> Any:
        """按点号路径取值，如 get('checkout.totalPrice.gross.amount')。

        路径中的数字段会被当作列表下标，如 get('products.edges.0.node.name')。
        """
        cur: Any = self.data
        for part in path.split("."):
            if isinstance(cur, dict):
                cur = cur.get(part)
            elif isinstance(cur, list):
                try:
                    cur = cur[int(part)]
                except (ValueError, IndexError):
                    return default
            else:
                return default
            if cur is None:
                return default
        return cur

    def brief(self) -> str:
        """单行摘要，用于日志与失败信息。"""
        if self.has_errors:
            return "HTTP %s | %sms | GraphQL errors: %s" % (
                self.status_code,
                round(self.elapsed_ms),
                "; ".join(self.error_messages())[:200],
            )
        return "HTTP %s | %sms | data keys: %s" % (
            self.status_code,
            round(self.elapsed_ms),
            list((self.data or {}).keys()),
        )

    def __repr__(self) -> str:
        return "<GraphQLResponse %s>" % self.brief()