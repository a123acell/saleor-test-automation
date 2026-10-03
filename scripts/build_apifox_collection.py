# -*- coding: utf-8 -*-
"""生成可导入 Apifox / Postman 的 GraphQL 集合（Postman Collection v2.1）。

请求内容全部来自 probe_core_flow.py 实测通过的链路。
输出：apifox/saleor-graphql.postman_collection.json
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "apifox", "saleor-graphql.postman_collection.json")

BASE_URL = "{{baseUrl}}/graphql/"

ADDRESS = {
    "firstName": "San",
    "lastName": "Zhang",
    "streetAddress1": "123 Test Road",
    "city": "New York",
    "postalCode": "10001",
    "country": "US",
    "countryArea": "NY",
    "phone": "+12125550000",
}


def req(name, query, variables=None, description="", test_script=None, auth=True, pre_script=None):
    headers = [{"key": "Content-Type", "value": "application/json"}]
    if auth:
        headers.append({"key": "Authorization", "value": "Bearer {{token}}"})
    item = {
        "name": name,
        "request": {
            "method": "POST",
            "header": headers,
            "body": {
                "mode": "graphql",
                "graphql": {
                    "query": query.strip(),
                    "variables": json.dumps(variables or {}, ensure_ascii=False, indent=2),
                },
            },
            "url": {"raw": BASE_URL, "host": ["{{baseUrl}}"], "path": ["graphql", ""]},
            "description": description,
        },
        "response": [],
    }
    events = []
    if pre_script:
        events.append({"listen": "prerequest", "script": {"type": "text/javascript", "exec": pre_script}})
    if test_script:
        events.append({"listen": "test", "script": {"type": "text/javascript", "exec": test_script}})
    if events:
        item["event"] = events
    return item


def folder(name, description, items):
    return {"name": name, "description": description, "item": items}


SAVE_TOKEN = [
    "var j = pm.response.json();",
    "var r = j.data && j.data.tokenCreate;",
    "pm.test('登录成功且无业务错误', function(){",
    "  pm.expect(r.errors, 'tokenCreate.errors').to.be.an('array').that.is.empty;",
    "});",
    "if (r && r.token) {",
    "  pm.collectionVariables.set('token', r.token);",
    "  if (r.refreshToken) { pm.collectionVariables.set('refreshToken', r.refreshToken); }",
    "}",
]

SAVE_VARIANT = [
    "var j = pm.response.json();",
    "var edges = j.data.products.edges;",
    "pm.test('商品列表非空', function(){ pm.expect(edges.length).to.be.above(0); });",
    "if (edges.length && edges[0].node.variants.length) {",
    "  pm.collectionVariables.set('variantId', edges[0].node.variants[0].id);",
    "}",
]

SAVE_CHECKOUT = [
    "var j = pm.response.json();",
    "var r = j.data.checkoutCreate;",
    "pm.test('创建购物车无业务错误', function(){",
    "  pm.expect(r.errors, 'checkoutCreate.errors').to.be.an('array').that.is.empty;",
    "});",
    "if (r.checkout) {",
    "  pm.collectionVariables.set('checkoutId', r.checkout.id);",
    "  pm.collectionVariables.set('checkoutToken', r.checkout.token);",
    "  pm.collectionVariables.set('checkoutTotal', r.checkout.totalPrice.gross.amount);",
    "}",
]

SAVE_CHECKOUT_DETAIL = [
    "var j = pm.response.json();",
    "var c = j.data.checkout;",
    "pm.test('购物车存在', function(){ pm.expect(c).to.not.be.null; });",
    "if (c) {",
    "  pm.collectionVariables.set('checkoutTotal', c.totalPrice.gross.amount);",
    "  if (c.lines.length) { pm.collectionVariables.set('lineId', c.lines[0].id); }",
    "  if (c.availableShippingMethods.length) {",
    "    pm.collectionVariables.set('shippingMethodId', c.availableShippingMethods[0].id);",
    "  }",
    "}",
]

SAVE_TOTAL_AFTER_DELIVERY = [
    "var j = pm.response.json();",
    "var r = j.data.checkoutDeliveryMethodUpdate;",
    "pm.test('选择配送方式无业务错误', function(){",
    "  pm.expect(r.errors, 'checkoutDeliveryMethodUpdate.errors').to.be.an('array').that.is.empty;",
    "});",
    "if (r.checkout) { pm.collectionVariables.set('checkoutTotal', r.checkout.totalPrice.gross.amount); }",
]

SAVE_ORDER = [
    "var j = pm.response.json();",
    "var r = j.data.checkoutComplete;",
    "pm.test('下单无业务错误', function(){",
    "  pm.expect(r.errors, 'checkoutComplete.errors').to.be.an('array').that.is.empty;",
    "});",
    "if (r.order) { pm.collectionVariables.set('orderId', r.order.id); }",
]

FOLDERS = [
    folder(
        "01 鉴权",
        "登录获取 Token，后续所有请求自动携带。",
        [
            req(
                "01 登录获取 Token",
                """
mutation TokenCreate($email: String!, $password: String!) {
  tokenCreate(email: $email, password: $password) {
    token
    refreshToken
    csrfToken
    user { id email isStaff }
    errors { field message code }
  }
}
""",
                {"email": "admin@example.com", "password": "admin"},
                "获取管理员 Token，测试脚本会把 token / refreshToken 写入集合变量。",
                SAVE_TOKEN,
                auth=False,
            ),
            req(
                "02 刷新 Token",
                """
mutation TokenRefresh($refreshToken: String!) {
  tokenRefresh(refreshToken: $refreshToken) {
    token
    errors { field message code }
  }
}
""",
                {"refreshToken": "{{refreshToken}}"},
                "用 refreshToken 换取新的访问 Token。",
            ),
            req(
                "03 校验 Token",
                """
mutation TokenVerify($token: String!) {
  tokenVerify(token: $token) {
    isValid
    payload
    errors { field message code }
  }
}
""",
                {"token": "{{token}}"},
                "校验 Token 有效性，返回 isValid 与 payload。",
            ),
        ],
    ),
    folder(
        "02 商品",
        "渠道、商品列表与商品详情查询。",
        [
            req(
                "04 渠道列表",
                """
query Channels {
  channels {
    id
    slug
    name
    currencyCode
    isActive
    defaultCountry { code country }
  }
}
""",
                {},
                "查询全部销售渠道，下单时必须指定渠道 slug。",
            ),
            req(
                "05 商品列表（分页）",
                """
query Products($channel: String!, $first: Int!) {
  products(first: $first, channel: $channel) {
    totalCount
    edges {
      node {
        id
        name
        slug
        productType { name }
        variants {
          id
          name
          sku
          pricing { price { gross { amount currency } } }
        }
      }
    }
  }
}
""",
                {"channel": "default-channel", "first": 5},
                "分页查询渠道下商品及变体、价格。测试脚本会写入 variantId。",
                SAVE_VARIANT,
            ),
            req(
                "06 商品详情（按 slug）",
                """
query ProductDetail($slug: String!, $channel: String!) {
  product(slug: $slug, channel: $channel) {
    id
    name
    slug
    description
    pricing { priceRange { start { gross { amount currency } } } }
    variants { id name sku quantityAvailable }
  }
}
""",
                {"slug": "apple-juice", "channel": "default-channel"},
                "按 slug 查询单个商品详情。slug 可在「05 商品列表」响应中获取。",
            ),
        ],
    ),
    folder(
        "03 核心链路 · 购物车到下单",
        "按顺序执行即可完成一次完整下单。金额变量 checkoutTotal 会自动跟随购物车变化。",
        [
            req(
                "07 创建购物车（加购）",
                """
mutation CheckoutCreate($input: CheckoutCreateInput!) {
  checkoutCreate(input: $input) {
    checkout {
      id
      token
      email
      totalPrice { gross { amount currency } }
      lines { id quantity variant { id name } }
    }
    errors { field message code }
  }
}
""",
                {
                    "input": {
                        "channel": "default-channel",
                        "email": "buyer@example.com",
                        "lines": [{"quantity": 1, "variantId": "{{variantId}}"}],
                    }
                },
                "创建购物车并加入商品。测试脚本写入 checkoutId / checkoutToken / checkoutTotal。",
                SAVE_CHECKOUT,
            ),
            req(
                "08 填写收货地址",
                """
mutation CheckoutShippingAddressUpdate($id: ID!, $shippingAddress: AddressInput!) {
  checkoutShippingAddressUpdate(id: $id, shippingAddress: $shippingAddress) {
    checkout {
      id
      shippingAddress { firstName lastName streetAddress1 city postalCode country { code } }
    }
    errors { field message code }
  }
}
""",
                {"id": "{{checkoutId}}", "shippingAddress": ADDRESS},
                "填写收货地址。注意：部分国家（如 CN）会校验 city / countryArea 合法性，不通过时返回 INVALID。",
            ),
            req(
                "09 填写账单地址",
                """
mutation CheckoutBillingAddressUpdate($id: ID!, $billingAddress: AddressInput!) {
  checkoutBillingAddressUpdate(id: $id, billingAddress: $billingAddress) {
    checkout { id billingAddress { city country { code } } }
    errors { field message code }
  }
}
""",
                {"id": "{{checkoutId}}", "billingAddress": ADDRESS},
                "填写账单地址。Saleor 要求下单前账单地址非空，否则返回 BILLING_ADDRESS_NOT_SET。",
            ),
            req(
                "10 查询购物车详情（取配送方式）",
                """
query CheckoutDetail($id: ID!) {
  checkout(id: $id) {
    id
    email
    totalPrice { gross { amount currency } }
    subtotalPrice { gross { amount currency } }
    lines { id quantity variant { id name } }
    availableShippingMethods { id name price { amount currency } }
    availablePaymentGateways { id name }
  }
}
""",
                {"id": "{{checkoutId}}"},
                "查询购物车明细、可用配送方式与支付网关。必须先填收货地址，否则 availableShippingMethods 为空。"
                "测试脚本写入 lineId / shippingMethodId / checkoutTotal。",
                SAVE_CHECKOUT_DETAIL,
            ),
            req(
                "11 选择配送方式",
                """
mutation CheckoutDeliveryMethodUpdate($id: ID!, $deliveryMethodId: ID!) {
  checkoutDeliveryMethodUpdate(id: $id, deliveryMethodId: $deliveryMethodId) {
    checkout {
      id
      shippingMethod { id name }
      totalPrice { gross { amount currency } }
    }
    errors { field message code }
  }
}
""",
                {"id": "{{checkoutId}}", "deliveryMethodId": "{{shippingMethodId}}"},
                "选择配送方式。shippingMethodId 由「08 查询购物车详情」自动写入。运费会计入总额，测试脚本会刷新 checkoutTotal。",
                SAVE_TOTAL_AFTER_DELIVERY,
            ),
            req(
                "12 创建支付",
                """
mutation CheckoutPaymentCreate($id: ID!, $input: PaymentInput!) {
  checkoutPaymentCreate(id: $id, input: $input) {
    payment { id total { amount currency } }
    errors { field message code }
  }
}
""",
                {
                    "id": "{{checkoutId}}",
                    "input": {"gateway": "mirumee.payments.dummy", "amount": "{{checkoutTotal}}", "token": "charged"},
                },
                "创建支付。Dummy 网关 token 可取 charged（成功）/ refused（拒绝）/ pending（待处理），用于模拟支付结果。",
            ),
            req(
                "13 完成下单",
                """
mutation CheckoutComplete($id: ID!) {
  checkoutComplete(id: $id) {
    order { id number status total { gross { amount currency } } }
    confirmationNeeded
    confirmationData
    errors { field message code }
  }
}
""",
                {"id": "{{checkoutId}}"},
                "完成下单。测试脚本写入 orderId。",
                SAVE_ORDER,
            ),
        ],
    ),
    folder(
        "04 订单",
        "订单查询（需管理员 Token）。",
        [
            req(
                "14 订单列表",
                """
query Orders($first: Int!) {
  orders(first: $first) {
    totalCount
    edges { node { id number status created total { gross { amount currency } } } }
  }
}
""",
                {"first": 10},
                "分页查询订单列表。",
            ),
            req(
                "15 订单详情",
                """
query OrderDetail($id: ID!) {
  order(id: $id) {
    id
    number
    status
    created
    userEmail
    total { gross { amount currency } }
    lines { id productName quantity }
  }
}
""",
                {"id": "{{orderId}}"},
                "按 ID 查询订单详情。orderId 由「13 完成下单」自动写入。",
            ),
        ],
    ),
    folder(
        "05 账户",
        "用户注册与当前用户信息。",
        [
            req(
                "16 当前用户信息",
                """
query Me {
  me {
    id
    email
    firstName
    lastName
    isStaff
    isActive
  }
}
""",
                {},
                "查询当前 Token 对应的用户信息。",
            ),
            req(
                "17 账户注册",
                """
mutation AccountRegister($input: AccountRegisterInput!) {
  accountRegister(input: $input) {
    user { id email isActive }
    errors { field message code }
  }
}
""",
                {"input": {"email": "{{registerEmail}}", "password": "Passw0rd!2026", "channel": "default-channel",
                           "redirectUrl": "http://localhost:3000/confirm"}},
                "注册新用户。Saleor 要求提供 redirectUrl（用于拼接邮箱确认链接），缺失会返回 REQUIRED。"
                "默认需邮箱确认后才激活，确认邮件可在 Mailpit（http://localhost:8025）查看。"
                "预请求脚本会生成随机邮箱，保证可重复执行。",
                pre_script=[
                    "pm.collectionVariables.set('registerEmail', 'autotest_' + Date.now() + '@example.com');",
                ],
            ),
        ],
    ),
    folder(
        "06 购物车扩展操作",
        "会改变购物车状态，建议在新建的购物车上单独验证，不要插在核心链路中间执行。",
        [
            req(
                "18 修改商品数量",
                """
mutation CheckoutLinesUpdate($id: ID!, $lines: [CheckoutLineUpdateInput!]!) {
  checkoutLinesUpdate(id: $id, lines: $lines) {
    checkout { id totalPrice { gross { amount currency } } lines { id quantity } }
    errors { field message code }
  }
}
""",
                {"id": "{{checkoutId}}", "lines": [{"lineId": "{{lineId}}", "quantity": 2}]},
                "修改购物车某行数量。lineId 由「08 查询购物车详情」自动写入。",
            ),
            req(
                "19 删除商品",
                """
mutation CheckoutLinesDelete($id: ID!, $linesIds: [ID!]!) {
  checkoutLinesDelete(id: $id, linesIds: $linesIds) {
    checkout { id totalPrice { gross { amount currency } } }
    errors { field message code }
  }
}
""",
                {"id": "{{checkoutId}}", "linesIds": ["{{lineId}}"]},
                "删除购物车中的商品行。",
            ),
        ],
    ),
]


def main():
    collection = {
        "info": {
            "name": "Saleor GraphQL 接口测试集合",
            "description": (
                "Saleor 电商平台 GraphQL 接口集合，覆盖鉴权、商品、购物车、结算下单、订单、账户六大模块，"
                "共 19 个请求。\n\n"
                "导入方式：Apifox → 项目设置 → 导入数据 → Postman → 选择本文件。\n\n"
                "执行顺序：按文件夹编号执行「01 鉴权」→「02 商品」→「03 核心链路」，"
                "即可自动完成一次完整下单。\n\n"
                "变量说明（均由测试脚本自动写入，无需手工填）：\n"
                "- baseUrl：Saleor 地址，默认 http://localhost:8000\n"
                "- token / refreshToken：登录后写入\n"
                "- variantId：查询商品列表后写入\n"
                "- checkoutId / checkoutToken / checkoutTotal：创建购物车后写入，选配送方式后刷新\n"
                "- lineId / shippingMethodId：查询购物车详情后写入\n"
                "- orderId：完成下单后写入"
            ),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "variable": [
            {"key": "baseUrl", "value": "http://localhost:8000"},
            {"key": "token", "value": ""},
            {"key": "refreshToken", "value": ""},
            {"key": "variantId", "value": ""},
            {"key": "checkoutId", "value": ""},
            {"key": "checkoutToken", "value": ""},
            {"key": "checkoutTotal", "value": ""},
            {"key": "lineId", "value": ""},
            {"key": "shippingMethodId", "value": ""},
            {"key": "orderId", "value": ""},
            {"key": "registerEmail", "value": ""},
        ],
        "item": FOLDERS,
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(collection, f, ensure_ascii=False, indent=2)

    total = sum(len(fo["item"]) for fo in FOLDERS)
    print("已生成：%s" % OUT)
    print("文件夹 %d 个，请求 %d 个：" % (len(FOLDERS), total))
    for fo in FOLDERS:
        print("  [%s] %d 个" % (fo["name"], len(fo["item"])))
        for r in fo["item"]:
            print("      - %s" % r["name"])


if __name__ == "__main__":
    main()