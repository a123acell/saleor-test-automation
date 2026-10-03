# -*- coding: utf-8 -*-
"""结算下单模块用例。

断言目标（错误码 / 字段）均经 scripts/probe 实证，与本地 Saleor 3.23 真实行为一致：
- 未填收货地址 -> availableShippingMethods 为空
- 未填账单地址 -> BILLING_ADDRESS_NOT_SET（field=billingAddress）
- 未足额支付   -> CHECKOUT_NOT_FULLY_PAID
- Dummy 缺 token -> REQUIRED（field=token）
- 支付金额不足 -> PARTIAL_PAYMENT_NOT_ALLOWED（field=amount）
- 非法手机号   -> INVALID（field=phone）
"""
import pytest

from common import assert_all, assert_biz_error, money, money_add, money_equal, queries
from common.assertions import assert_no_graphql_errors
from common.flows import DEFAULT_ADDRESS, DUMMY_GATEWAY


@pytest.mark.checkout
@pytest.mark.smoke
def test_CHECKOUT_001_shipping_address_success(client, checkout):
    """CHECKOUT-001 填写收货地址成功，城市名被规范化。"""
    resp = client.mutate(
        queries.CHECKOUT_SHIPPING_ADDRESS_UPDATE,
        {"id": checkout["id"], "shippingAddress": DEFAULT_ADDRESS},
    )
    assert_all(resp, "checkoutShippingAddressUpdate")
    city = resp.get("checkoutShippingAddressUpdate.checkout.shippingAddress.city")
    assert city.upper() == DEFAULT_ADDRESS["city"].upper(), "城市名应与提交值一致（大小写可规范化）"
    assert (
        resp.get("checkoutShippingAddressUpdate.checkout.shippingAddress.country.code") == "US"
    )


@pytest.mark.checkout
def test_CHECKOUT_002_shipping_methods_require_address(client, checkout):
    """CHECKOUT-002 未填收货地址时无可用配送方式，填后可用（依赖顺序验证）。"""
    before = client.query(queries.CHECKOUT_QUERY, {"id": checkout["id"]})
    assert_all(before, "checkout")
    assert (before.get("checkout.availableShippingMethods") or []) == [], (
        "未填收货地址时可用配送方式应为空"
    )

    client.mutate(
        queries.CHECKOUT_SHIPPING_ADDRESS_UPDATE,
        {"id": checkout["id"], "shippingAddress": DEFAULT_ADDRESS},
    )
    after = client.query(queries.CHECKOUT_QUERY, {"id": checkout["id"]})
    methods = after.get("checkout.availableShippingMethods") or []
    assert len(methods) > 0, "填收货地址后应出现可用配送方式"


@pytest.mark.checkout
def test_CHECKOUT_003_billing_address_success(client, checkout):
    """CHECKOUT-003 填写账单地址成功。"""
    resp = client.mutate(
        queries.CHECKOUT_BILLING_ADDRESS_UPDATE,
        {"id": checkout["id"], "billingAddress": DEFAULT_ADDRESS},
    )
    assert_all(resp, "checkoutBillingAddressUpdate")
    assert (
        resp.get("checkoutBillingAddressUpdate.checkout.billingAddress.country.code") == "US"
    )


@pytest.mark.checkout
def test_CHECKOUT_004_delivery_method_updates_total(client, checkout):
    """CHECKOUT-004 选择配送方式后，应付金额 = 商品金额 + 运费。"""
    client.mutate(
        queries.CHECKOUT_SHIPPING_ADDRESS_UPDATE,
        {"id": checkout["id"], "shippingAddress": DEFAULT_ADDRESS},
    )
    before = client.query(queries.CHECKOUT_QUERY, {"id": checkout["id"]})
    goods_total = before.get("checkout.totalPrice.gross.amount")
    methods = before.get("checkout.availableShippingMethods") or []
    assert methods, "应存在可用配送方式"

    # 选运费最高的方式，确保金额变化可观测
    target = max(methods, key=lambda m: money(m["price"]["amount"]))
    fee = target["price"]["amount"]

    resp = client.mutate(
        queries.CHECKOUT_DELIVERY_METHOD_UPDATE,
        {"id": checkout["id"], "deliveryMethodId": target["id"]},
    )
    assert_all(resp, "checkoutDeliveryMethodUpdate")
    actual = resp.get("checkoutDeliveryMethodUpdate.checkout.totalPrice.gross.amount")
    expected = money_add(goods_total, fee)
    assert money_equal(actual, expected), (
        "选配送后金额期望 %s（商品 %s + 运费 %s），实际 %s"
        % (expected, goods_total, fee, actual)
    )
    assert resp.get("checkoutDeliveryMethodUpdate.checkout.shippingMethod.name") == target["name"]


@pytest.mark.checkout
@pytest.mark.smoke
def test_CHECKOUT_005_payment_create_success(client, checkout):
    """CHECKOUT-005 足额支付创建成功，网关与金额正确。"""
    client.mutate(
        queries.CHECKOUT_SHIPPING_ADDRESS_UPDATE,
        {"id": checkout["id"], "shippingAddress": DEFAULT_ADDRESS},
    )
    client.mutate(
        queries.CHECKOUT_BILLING_ADDRESS_UPDATE,
        {"id": checkout["id"], "billingAddress": DEFAULT_ADDRESS},
    )
    info = client.query(queries.CHECKOUT_QUERY, {"id": checkout["id"]})
    methods = info.get("checkout.availableShippingMethods") or []
    client.mutate(
        queries.CHECKOUT_DELIVERY_METHOD_UPDATE,
        {"id": checkout["id"], "deliveryMethodId": methods[0]["id"]},
    )
    total = client.query(queries.CHECKOUT_QUERY, {"id": checkout["id"]}).get(
        "checkout.totalPrice.gross.amount"
    )

    resp = client.mutate(
        queries.CHECKOUT_PAYMENT_CREATE,
        {"id": checkout["id"], "input": {"gateway": DUMMY_GATEWAY, "amount": total, "token": "charged"}},
    )
    assert_all(resp, "checkoutPaymentCreate")
    assert resp.get("checkoutPaymentCreate.payment.gateway") == DUMMY_GATEWAY
    assert money_equal(resp.get("checkoutPaymentCreate.payment.total.amount"), total)
    # Dummy 网关不会真正扣款，创建后扣款状态为 NOT_CHARGED（实证）
    assert resp.get("checkoutPaymentCreate.payment.chargeStatus") == "NOT_CHARGED"


@pytest.mark.checkout
@pytest.mark.negative
def test_CHECKOUT_006_payment_without_billing_address(client, checkout):
    """CHECKOUT-006 未填账单地址创建支付，返回 BILLING_ADDRESS_NOT_SET。"""
    client.mutate(
        queries.CHECKOUT_SHIPPING_ADDRESS_UPDATE,
        {"id": checkout["id"], "shippingAddress": DEFAULT_ADDRESS},
    )
    info = client.query(queries.CHECKOUT_QUERY, {"id": checkout["id"]})
    methods = info.get("checkout.availableShippingMethods") or []
    client.mutate(
        queries.CHECKOUT_DELIVERY_METHOD_UPDATE,
        {"id": checkout["id"], "deliveryMethodId": methods[0]["id"]},
    )
    total = client.query(queries.CHECKOUT_QUERY, {"id": checkout["id"]}).get(
        "checkout.totalPrice.gross.amount"
    )

    resp = client.mutate(
        queries.CHECKOUT_PAYMENT_CREATE,
        {"id": checkout["id"], "input": {"gateway": DUMMY_GATEWAY, "amount": total, "token": "charged"}},
    )
    assert_no_graphql_errors(resp)
    assert_biz_error(resp, "checkoutPaymentCreate", code="BILLING_ADDRESS_NOT_SET")


@pytest.mark.checkout
@pytest.mark.negative
def test_CHECKOUT_007_complete_without_payment(client, checkout):
    """CHECKOUT-007 未支付直接下单，返回 CHECKOUT_NOT_FULLY_PAID。"""
    client.mutate(
        queries.CHECKOUT_SHIPPING_ADDRESS_UPDATE,
        {"id": checkout["id"], "shippingAddress": DEFAULT_ADDRESS},
    )
    client.mutate(
        queries.CHECKOUT_BILLING_ADDRESS_UPDATE,
        {"id": checkout["id"], "billingAddress": DEFAULT_ADDRESS},
    )
    info = client.query(queries.CHECKOUT_QUERY, {"id": checkout["id"]})
    methods = info.get("checkout.availableShippingMethods") or []
    client.mutate(
        queries.CHECKOUT_DELIVERY_METHOD_UPDATE,
        {"id": checkout["id"], "deliveryMethodId": methods[0]["id"]},
    )

    resp = client.mutate(queries.CHECKOUT_COMPLETE, {"id": checkout["id"]})
    assert_no_graphql_errors(resp)
    assert_biz_error(resp, "checkoutComplete", code="CHECKOUT_NOT_FULLY_PAID")


@pytest.mark.checkout
@pytest.mark.negative
def test_CHECKOUT_008_dummy_gateway_requires_token(client, checkout):
    """CHECKOUT-008 Dummy 网关不传 token，返回 REQUIRED（field=token）。"""
    client.mutate(
        queries.CHECKOUT_SHIPPING_ADDRESS_UPDATE,
        {"id": checkout["id"], "shippingAddress": DEFAULT_ADDRESS},
    )
    client.mutate(
        queries.CHECKOUT_BILLING_ADDRESS_UPDATE,
        {"id": checkout["id"], "billingAddress": DEFAULT_ADDRESS},
    )
    info = client.query(queries.CHECKOUT_QUERY, {"id": checkout["id"]})
    methods = info.get("checkout.availableShippingMethods") or []
    client.mutate(
        queries.CHECKOUT_DELIVERY_METHOD_UPDATE,
        {"id": checkout["id"], "deliveryMethodId": methods[0]["id"]},
    )
    total = client.query(queries.CHECKOUT_QUERY, {"id": checkout["id"]}).get(
        "checkout.totalPrice.gross.amount"
    )

    resp = client.mutate(
        queries.CHECKOUT_PAYMENT_CREATE,
        {"id": checkout["id"], "input": {"gateway": DUMMY_GATEWAY, "amount": total}},
    )
    assert_no_graphql_errors(resp)
    assert_biz_error(resp, "checkoutPaymentCreate", code="REQUIRED", field="token")


@pytest.mark.checkout
@pytest.mark.negative
def test_CHECKOUT_009_partial_payment_not_allowed(client, checkout):
    """CHECKOUT-009 支付金额小于应付总额，返回 PARTIAL_PAYMENT_NOT_ALLOWED。"""
    client.mutate(
        queries.CHECKOUT_SHIPPING_ADDRESS_UPDATE,
        {"id": checkout["id"], "shippingAddress": DEFAULT_ADDRESS},
    )
    client.mutate(
        queries.CHECKOUT_BILLING_ADDRESS_UPDATE,
        {"id": checkout["id"], "billingAddress": DEFAULT_ADDRESS},
    )
    info = client.query(queries.CHECKOUT_QUERY, {"id": checkout["id"]})
    methods = info.get("checkout.availableShippingMethods") or []
    client.mutate(
        queries.CHECKOUT_DELIVERY_METHOD_UPDATE,
        {"id": checkout["id"], "deliveryMethodId": methods[0]["id"]},
    )

    resp = client.mutate(
        queries.CHECKOUT_PAYMENT_CREATE,
        {"id": checkout["id"], "input": {"gateway": DUMMY_GATEWAY, "amount": "0.01", "token": "charged"}},
    )
    assert_no_graphql_errors(resp)
    assert_biz_error(resp, "checkoutPaymentCreate", code="PARTIAL_PAYMENT_NOT_ALLOWED", field="amount")


@pytest.mark.checkout
@pytest.mark.negative
def test_CHECKOUT_010_invalid_phone_rejected(client, checkout):
    """CHECKOUT-010 非法手机号填写收货地址，返回 INVALID（field=phone）。"""
    bad_address = dict(DEFAULT_ADDRESS)
    bad_address["phone"] = "+86215550000"  # 实证：该号码不被接受
    resp = client.mutate(
        queries.CHECKOUT_SHIPPING_ADDRESS_UPDATE,
        {"id": checkout["id"], "shippingAddress": bad_address},
    )
    assert_no_graphql_errors(resp)
    assert_biz_error(resp, "checkoutShippingAddressUpdate", code="INVALID", field="phone")


@pytest.mark.checkout
@pytest.mark.smoke
def test_CHECKOUT_011_full_flow_creates_order(client, channel_slug, variant):
    """CHECKOUT-011 完整链路下单成功，生成订单且状态为未履约。"""
    from common.flows import build_order

    order = build_order(client, channel_slug, variant["variant_id"], quantity=1)
    assert order.get("id"), "订单应返回 id"
    assert order.get("number"), "订单应返回订单号"
    assert order.get("status") == "UNFULFILLED", "新订单状态应为 UNFULFILLED，实际 %s" % order.get("status")
    assert money(order["total"]["gross"]["amount"]) > 0, "订单金额应大于 0"


@pytest.mark.checkout
def test_CHECKOUT_012_refused_token_still_completes(client, checkout):
    """CHECKOUT-012 refused 令牌：金额已覆盖，仍可完成下单（Dummy 网关不校验扣款状态）。"""
    client.mutate(
        queries.CHECKOUT_SHIPPING_ADDRESS_UPDATE,
        {"id": checkout["id"], "shippingAddress": DEFAULT_ADDRESS},
    )
    client.mutate(
        queries.CHECKOUT_BILLING_ADDRESS_UPDATE,
        {"id": checkout["id"], "billingAddress": DEFAULT_ADDRESS},
    )
    info = client.query(queries.CHECKOUT_QUERY, {"id": checkout["id"]})
    methods = info.get("checkout.availableShippingMethods") or []
    client.mutate(
        queries.CHECKOUT_DELIVERY_METHOD_UPDATE,
        {"id": checkout["id"], "deliveryMethodId": methods[0]["id"]},
    )
    total = client.query(queries.CHECKOUT_QUERY, {"id": checkout["id"]}).get(
        "checkout.totalPrice.gross.amount"
    )

    pay = client.mutate(
        queries.CHECKOUT_PAYMENT_CREATE,
        {"id": checkout["id"], "input": {"gateway": DUMMY_GATEWAY, "amount": total, "token": "refused"}},
    )
    assert_all(pay, "checkoutPaymentCreate")
    assert pay.get("checkoutPaymentCreate.payment.chargeStatus") == "NOT_CHARGED"

    done = client.mutate(queries.CHECKOUT_COMPLETE, {"id": checkout["id"]})
    assert_no_graphql_errors(done)
    assert done.payload_errors("checkoutComplete") == [], (
        "refused 令牌下金额已覆盖，下单不应报错，实际 %s"
        % done.payload_error_messages("checkoutComplete")
    )
    assert done.get("checkoutComplete.order") is not None, "应生成订单"