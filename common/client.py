# -*- coding: utf-8 -*-
"""统一 GraphQL 请求层。

设计要点：
- 复用 requests.Session（连接池复用，避免每条用例新建连接）
- 统一 base url / 超时 / Content-Type / Bearer Token
- 每次请求记录耗时（毫秒），供性能阈值断言使用
- 记录最近请求历史，用例失败时可回溯
- Token 失效时自动重新登录并重试一次（需先 set_credentials）
- 登录被环境限流时自动等待解封后重试

关于登录限流：Saleor 对同一 IP 的失败登录会逐次指数延长封禁
（同一用户第 1 次失败封 1s、第 2 次 2s、第 3 次 4s…），登录成功即清零。
框架在 login() 内识别该提示并等待解封，避免用例因环境安全机制而假失败。
"""
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

import config
from common.logger import get_logger
from common.queries import TOKEN_CREATE
from common.response import GraphQLResponse

log = get_logger("saleor.client")

# 出现这些 GraphQL 错误码时，认为 Token 失效，触发自动重登
_AUTH_ERROR_CODES = {"UNAUTHENTICATED", "JWT_INVALID_TOKEN", "JWT_EXPIRED", "FORBIDDEN"}
_AUTH_ERROR_KEYWORDS = ("Signature has expired", "Invalid token", "not authenticated")

# 登录限流提示特征
_THROTTLE_KEYWORD = "logging has been suspended"
_THROTTLE_STAMP_RE = re.compile(r"suspended till (\S+ \S+)", re.IGNORECASE)


def is_login_throttled(resp: GraphQLResponse) -> bool:
    """响应是否属于「登录限流封禁」。"""
    messages = resp.payload_error_messages("tokenCreate") or resp.error_messages()
    return any(_THROTTLE_KEYWORD in m.lower() for m in messages)


def seconds_until_login_unblocked(resp: GraphQLResponse, default: float = 2.0, cap: float = 60.0) -> float:
    """解析限流提示中的解封时间，返回还需等待的秒数。"""
    messages = resp.payload_error_messages("tokenCreate") or resp.error_messages()
    for msg in messages:
        match = _THROTTLE_STAMP_RE.search(msg)
        if not match:
            continue
        try:
            unblock_at = datetime.fromisoformat(match.group(1))
        except ValueError:
            continue
        if unblock_at.tzinfo is None:
            unblock_at = unblock_at.replace(tzinfo=timezone.utc)
        delta = (unblock_at - datetime.now(timezone.utc)).total_seconds()
        return max(0.0, min(delta + 0.5, cap))
    return default


class GraphQLClient:
    """GraphQL 请求客户端。"""

    def __init__(
        self,
        url: Optional[str] = None,
        timeout: Optional[int] = None,
        token: Optional[str] = None,
        auto_reauth: bool = True,
    ):
        self.url = url or config.GRAPHQL_URL
        self.timeout = timeout or config.TIMEOUT
        self.auto_reauth = auto_reauth
        self.token = token
        self.refresh_token: Optional[str] = None

        self._email: Optional[str] = None
        self._password: Optional[str] = None

        self.session = requests.Session()
        self.session.headers.update(
            {"Content-Type": "application/json", "Accept": "application/json"}
        )

        # 最近请求历史（最多保留 50 条）
        self.history: List[Dict[str, Any]] = []
        self._history_limit = 50

    # ---------------- Token 管理 ----------------

    def set_token(self, token: Optional[str]) -> None:
        self.token = token

    def clear_token(self) -> None:
        self.token = None

    def set_credentials(self, email: str, password: str) -> None:
        """登记账号密码，供 Token 失效时自动重登。"""
        self._email = email
        self._password = password

    def login(self, email: Optional[str] = None, password: Optional[str] = None, max_retries: int = 4) -> str:
        """登录并写入 self.token，返回 Token。

        若命中环境登录限流，会等待解封后重试（最多 max_retries 次）。
        """
        email = email or self._email or config.ADMIN_EMAIL
        password = password if password is not None else (
            self._password if self._password is not None else config.ADMIN_PASSWORD
        )

        last_resp: Optional[GraphQLResponse] = None
        for _ in range(max_retries):
            resp = self.execute(
                TOKEN_CREATE,
                {"email": email, "password": password},
                use_auth=False,
                _skip_reauth=True,
            )
            last_resp = resp
            errors = resp.payload_errors("tokenCreate")

            if errors and is_login_throttled(resp):
                wait = seconds_until_login_unblocked(resp)
                log.warning("登录被环境限流，等待 %.1fs 后重试", wait)
                time.sleep(wait)
                continue

            if errors:
                raise RuntimeError(
                    "登录失败：%s" % resp.payload_error_messages("tokenCreate")
                )

            token = resp.get("tokenCreate.token")
            if not token:
                raise RuntimeError("登录未返回 token：%s" % resp.brief())

            self.token = token
            self.refresh_token = resp.get("tokenCreate.refreshToken")
            self._email, self._password = email, password
            log.info("登录成功，token 长度 %d", len(token))
            return token

        raise RuntimeError(
            "登录连续被限流，已重试 %d 次：%s"
            % (max_retries, last_resp.brief() if last_resp else "无响应")
        )

    # ---------------- 请求发送 ----------------

    def _headers(self, token: Optional[str], extra: Optional[Dict[str, str]]) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        if token:
            headers["Authorization"] = "Bearer " + token
        if extra:
            headers.update(extra)
        return headers

    def execute(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None,
        token: Optional[str] = None,
        use_auth: bool = True,
        timeout: Optional[int] = None,
        extra_headers: Optional[Dict[str, str]] = None,
        _skip_reauth: bool = False,
    ) -> GraphQLResponse:
        """发送一次 GraphQL 请求并返回封装后的响应。

        use_auth=True 时自动携带 self.token；token 参数可临时覆盖。
        """
        effective_token = token if token is not None else (self.token if use_auth else None)

        body: Dict[str, Any] = {"query": query}
        if variables:
            body["variables"] = variables
        if operation_name:
            body["operationName"] = operation_name

        resp = self._post(body, effective_token, timeout, extra_headers)

        # Token 失效时自动重登并重试一次
        if (
            use_auth
            and not _skip_reauth
            and self.auto_reauth
            and self._email
            and self._is_auth_error(resp)
        ):
            log.warning("检测到 Token 失效，自动重新登录后重试")
            self.login()
            resp = self._post(body, self.token, timeout, extra_headers)

        return resp

    def _post(
        self,
        body: Dict[str, Any],
        token: Optional[str],
        timeout: Optional[int],
        extra_headers: Optional[Dict[str, str]],
    ) -> GraphQLResponse:
        start = time.perf_counter()
        try:
            raw = self.session.post(
                self.url,
                json=body,
                headers=self._headers(token, extra_headers),
                timeout=timeout or self.timeout,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            try:
                payload = raw.json()
            except ValueError:
                payload = None
            result = GraphQLResponse(
                status_code=raw.status_code,
                payload=payload,
                elapsed_ms=elapsed_ms,
                request_body=body,
                raw_text=raw.text[:2000] if payload is None else "",
            )
        except requests.RequestException as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            log.error("请求异常：%s", exc)
            result = GraphQLResponse(
                status_code=0,
                payload={"errors": [{"message": "请求异常：%s" % exc}]},
                elapsed_ms=elapsed_ms,
                request_body=body,
            )

        self._record(body, result)
        return result

    def _record(self, body: Dict[str, Any], resp: GraphQLResponse) -> None:
        self.history.append(
            {
                "query": (body.get("query") or "").strip().splitlines()[0][:120],
                "variables": body.get("variables"),
                "status_code": resp.status_code,
                "elapsed_ms": round(resp.elapsed_ms, 1),
                "has_errors": resp.has_errors,
            }
        )
        if len(self.history) > self._history_limit:
            self.history = self.history[-self._history_limit:]

    @staticmethod
    def _is_auth_error(resp: GraphQLResponse) -> bool:
        if resp.status_code in (401, 403):
            return True
        if set(resp.error_codes()) & _AUTH_ERROR_CODES:
            return True
        joined = " ".join(resp.error_messages())
        return any(kw in joined for kw in _AUTH_ERROR_KEYWORDS)

    # ---------------- 便捷方法 ----------------

    def query(self, query: str, variables: Optional[Dict[str, Any]] = None, **kwargs: Any) -> GraphQLResponse:
        return self.execute(query, variables, **kwargs)

    def mutate(self, mutation: str, variables: Optional[Dict[str, Any]] = None, **kwargs: Any) -> GraphQLResponse:
        return self.execute(mutation, variables, **kwargs)

    def close(self) -> None:
        self.session.close()