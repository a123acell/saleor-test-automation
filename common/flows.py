# -*- coding: utf-8 -*-
"""业务链路封装（数据构造层）。

把「查渠道 -> 取变体 -> 建购物车 -> 填地址 -> 选配送 -> 支付 -> 下单」
这些多步操作封装成函数，用例只调用结果，不重复拼装 GraphQL。

所有函数在业务错误时抛 RuntimeError，保证前置数据构造失败能被立刻发现，
而不是让后续断言给出误导性的失败原因。
"""
import time
from typing import Any, Dict, Optional

from common import queries
from common.client import (
    GraphQLClient,
    is_login_throttled,
    seconds_until_login_unblocked,
)

# 美国地址：默认渠道默认国家为 US，且被配送区域覆盖，实测可用
# 注意：CN 地址会触发 city/countryArea 合法性校验，填写不当会返回 INVALID
DEFAULT_ADDRESS: Dict[str, str] = {
    "firstName": "San",
    "lastName": "Zhang",
    "streetAddress1": "123 Test Road",
    "city": "New York",
    "postalCode": "10001",
    "country": "US",
    "countryArea": "NY",
    "phone": "+12125550000",
}

DUMMY_GATEWAY = "mirumee.payments.dummy"


def _require_no_biz_error(resp, operation: str, context: str) -> Dict[str, Any]:
    node = resp.field(operation)
    if resp.has_errors:
        raise RuntimeError("%s 失败（GraphQL 错误）：%s" % (context, resp.error_messages()))
    if not isinstance(node, dict):
        raise RuntimeError("%s 失败：返回结构异常 %s" % (context, resp.brief()))
    errors = node.get("errors") or []
    if errors:
        raise RuntimeError(
            "%s 失败：%s" % (context, [e.get("message") for e in errors])
        )
    return node


def login_expect_failure(
    client: GraphQLClient,
    email: str,
    password: str,
    retries: int = 3,
):
    """发起一次「预期失败」的登录，返回最终的响应。

    若被环境登录限流拦截，会等待解封后重试，确保断言拿到的是
    真实的凭据校验结果，而不是限流提示。
    """
    resp = None
    for _ in range(retries):
        resp = client.execute(
            queries.TOKEN_CREATE,
            {"email": email, "password": password},
            use_auth=False,
        )
        if is_login_throttled(resp):
            time.sleep(seconds_until_login_unblocked(resp))
            continue
        return resp
    return resp


def get_channels(client: GraphQLClient) -> list:
    resp = client.query(queries.CHANNELS)
    if resp.has_errors:
        raise RuntimeError("查询渠道失败：%s" % resp.error_messages())
    return resp.get("channels") or []


def pick_channel(client: GraphQLClient, slug: Optional[str] = None) -> Dict[str, Any]:
    """按 slug 选渠道，未指定则取第一个可用渠道。"""
    channels = get_channels(client)
    if not channels:
        raise RuntimeError("当前环境没有可用渠道")
    if slug:
        for ch in channels:
            if ch.get("slug") == slug:
                return ch
        raise RuntimeError("未找到渠道 slug=%s，现有：%s" % (slug, [c.get("slug") for c in channels]))
    return channels[0]


def get_first_variant(client: GraphQLClient, channel: str, scan: int = 20) -> Dict[str, Any]:
    """取第一个「有定价」的商品变体，返回 id / 单价 / 所属商品。"""
    resp = client.query(queries.PRODUCTS, {"channel": channel, "first": scan})
    if resp.has_errors:
        raise RuntimeError("查询商品失败：%s" % resp.error_messages())
    edges = resp.get("products.edges") or []
    for edge in edges:
        node = edge.get("node") or {}
        for variant in node.get("variants") or []:
            price = (
                ((variant.get("pricing") or {}).get("price") or {}).get("gross")
            )
            if price and price.get("amount") is not None:
                return {
                    "variant_id": variant["id"],
                    "variant_name": variant.get("name"),
                    "sku": variant.get("sku"),
                    "product_id": node.get("id"),
                    "product_name": node.get("name"),
                    "price": price["amount"],
                    "currency": price["currency"],
                }
    raise RuntimeError("前 %d 个商品中没有带定价的变体" % scan)


def create_checkout(
    client: GraphQLClient,
    channel: str,
    variant_id: str,
    quantity: int = 1,
    email: str = "buyer@example.com",
    use_auth: bool = False,
) -> Dict[str, Any]:
    """创建购物车并加购，返回 checkout 对象。"""
    resp = client.execute(
        queries.CHECKOUT_CREATE,
        {
            "input": {
                "channel": channel,
                "email": email,
                "lines": [{"quantity": quantity, "variantId": variant_id}],
            }
        },
        use_auth=use_auth,
    )
    node = _require_no_biz_error(resp, "checkoutCreate", "创建购物车")
    checkout = node.get("checkout")
    if not checkout:
        raise RuntimeError("创建购物车失败：未返回 checkout")
    return checkout


def set_shipping_address(
    client: GraphQLClient, checkout_id: str, address: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    resp = client.mutate(
        queries.CHECKOUT_SHIPPING_ADDRESS_UPDATE,
        {"id": checkout_id, "shippingAddress": address or DEFAULT_ADDRESS},
    )
    return _require_no_biz_error(resp, "checkoutShippingAddressUpdate", "填写收货地址")


def set_billing_address(
    client: GraphQLClient, checkout_id: str, address: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    resp = client.mutate(
        queries.CHECKOUT_BILLING_ADDRESS_UPDATE,
        {"id": checkout_id, "billingAddress": address or DEFAULT_ADDRESS},
    )
    return _require_no_biz_error(resp, "checkoutBillingAddressUpdate", "填写账单地址")


def get_shipping_methods(client: GraphQLClient, checkout_id: str) -> list:
    resp = client.query(queries.CHECKOUT_QUERY, {"id": checkout_id})
    if resp.has_errors:
        raise RuntimeError("查询购物车失败：%s" % resp.error_messages())
    return resp.get("checkout.availableShippingMethods") or []


def select_delivery_method(client: GraphQLClient, checkout_id: str, method_id: str) -> Dict[str, Any]:
    resp = client.mutate(
        queries.CHECKOUT_DELIVERY_METHOD_UPDATE,
        {"id": checkout_id, "deliveryMethodId": method_id},
    )
    return _require_no_biz_error(resp, "checkoutDeliveryMethodUpdate", "选择配送方式")


def get_checkout_total(client: GraphQLClient, checkout_id: str) -> Dict[str, str]:
    resp = client.query(queries.CHECKOUT_QUERY, {"id": checkout_id})
    if resp.has_errors:
        raise RuntimeError("查询购物车金额失败：%s" % resp.error_messages())
    total = resp.get("checkout.totalPrice.gross")
    if not total:
        raise RuntimeError("购物车未返回应付金额")
    return total


def create_payment(
    client: GraphQLClient,
    checkout_id: str,
    amount: Optional[str] = None,
    gateway: str = DUMMY_GATEWAY,
    token: str = "charged",
) -> Dict[str, Any]:
    """创建支付。Dummy 网关必须传 token（charged/refused/pending）。"""
    if amount is None:
        amount = get_checkout_total(client, checkout_id)["amount"]
    resp = client.mutate(
        queries.CHECKOUT_PAYMENT_CREATE,
        {"id": checkout_id, "input": {"gateway": gateway, "amount": amount, "token": token}},
    )
    return _require_no_biz_error(resp, "checkoutPaymentCreate", "创建支付")


def complete_checkout(client: GraphQLClient, checkout_id: str) -> Dict[str, Any]:
    resp = client.mutate(queries.CHECKOUT_COMPLETE, {"id": checkout_id})
    return _require_no_biz_error(resp, "checkoutComplete", "完成下单")


def build_order(
    client: GraphQLClient,
    channel: str,
    variant_id: str,
    quantity: int = 1,
    address: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """走完整下单链路，返回订单对象。

    顺序严格遵循：建购物车 -> 收货地址 -> 账单地址 -> 查配送 -> 选配送 -> 支付 -> 下单。
    """
    checkout = create_checkout(client, channel, variant_id, quantity=quantity)
    checkout_id = checkout["id"]

    set_shipping_address(client, checkout_id, address)
    set_billing_address(client, checkout_id, address)

    methods = get_shipping_methods(client, checkout_id)
    if not methods:
        raise RuntimeError("无可用配送方式，无法下单（检查仓库配送区域配置）")
    select_delivery_method(client, checkout_id, methods[0]["id"])

    create_payment(client, checkout_id)
    node = complete_checkout(client, checkout_id)

    order = node.get("order")
    if not order:
        raise RuntimeError("下单失败：未返回 order")
    return order