# -*- coding: utf-8 -*-
"""GraphQL 语句集中管理。

所有 query / mutation 文档统一放这里，测试用例只引用常量 + 传变量，
做到「语句与用例分离」，改 schema 时只动这一处。

字段选择原则：
- 只取断言需要的字段，避免过度拉取
- 每个 mutation 都带 errors { field message code }，便于业务错误断言
"""

# ============================ 鉴权与令牌 ============================

TOKEN_CREATE = """
mutation TokenCreate($email: String!, $password: String!) {
  tokenCreate(email: $email, password: $password) {
    token
    refreshToken
    csrfToken
    user { id email isStaff }
    errors { field message code }
  }
}
"""

TOKEN_REFRESH = """
mutation TokenRefresh($refreshToken: String) {
  tokenRefresh(refreshToken: $refreshToken) {
    token
    errors { field message code }
  }
}
"""

TOKEN_VERIFY = """
mutation TokenVerify($token: String!) {
  tokenVerify(token: $token) {
    isValid
    payload
    errors { field message code }
  }
}
"""

# ============================ 渠道 ============================

CHANNELS = """
query Channels {
  channels {
    id
    slug
    name
    currencyCode
    isActive
  }
}
"""

# ============================ 商品与目录 ============================

PRODUCTS = """
query Products($channel: String!, $first: Int!) {
  products(first: $first, channel: $channel) {
    totalCount
    edges {
      node {
        id
        name
        slug
        variants {
          id
          name
          sku
          pricing {
            price { gross { amount currency } }
          }
        }
      }
    }
  }
}
"""

PRODUCT_BY_ID = """
query ProductById($id: ID!, $channel: String!) {
  product(id: $id, channel: $channel) {
    id
    name
    slug
    isAvailable
    variants {
      id
      name
      sku
      quantityAvailable
      pricing { price { gross { amount currency } } }
    }
  }
}
"""

PRODUCT_VARIANTS = """
query ProductVariants($channel: String!, $first: Int!) {
  productVariants(first: $first, channel: $channel) {
    totalCount
    edges {
      node {
        id
        name
        sku
        pricing { price { gross { amount currency } } }
      }
    }
  }
}
"""

CATEGORIES = """
query Categories($first: Int!) {
  categories(first: $first) {
    totalCount
    edges { node { id name slug } }
  }
}
"""

# ============================ 购物车与结算 ============================

CHECKOUT_CREATE = """
mutation CheckoutCreate($input: CheckoutCreateInput!) {
  checkoutCreate(input: $input) {
    checkout {
      id
      token
      email
      totalPrice { gross { amount currency } }
      lines { id quantity }
    }
    errors { field message code }
  }
}
"""

CHECKOUT_QUERY = """
query Checkout($id: ID!) {
  checkout(id: $id) {
    id
    token
    email
    quantity
    totalPrice { gross { amount currency } }
    lines { id quantity variant { id name } }
    shippingAddress { id city country { code } }
    billingAddress { id city country { code } }
    availableShippingMethods { id name price { amount currency } }
    availablePaymentGateways { id name }
    isShippingRequired
  }
}
"""

CHECKOUT_LINES_ADD = """
mutation CheckoutLinesAdd($id: ID!, $lines: [CheckoutLineInput!]!) {
  checkoutLinesAdd(id: $id, lines: $lines) {
    checkout {
      id
      quantity
      lines { id quantity }
      totalPrice { gross { amount currency } }
    }
    errors { field message code }
  }
}
"""

CHECKOUT_LINES_UPDATE = """
mutation CheckoutLinesUpdate($id: ID!, $lines: [CheckoutLineUpdateInput!]!) {
  checkoutLinesUpdate(id: $id, lines: $lines) {
    checkout {
      id
      quantity
      lines { id quantity }
      totalPrice { gross { amount currency } }
    }
    errors { field message code }
  }
}
"""

CHECKOUT_LINE_DELETE = """
mutation CheckoutLineDelete($id: ID!, $lineId: ID!) {
  checkoutLineDelete(id: $id, lineId: $lineId) {
    checkout { id lines { id quantity } }
    errors { field message code }
  }
}
"""

CHECKOUT_EMAIL_UPDATE = """
mutation CheckoutEmailUpdate($id: ID!, $email: String!) {
  checkoutEmailUpdate(id: $id, email: $email) {
    checkout { id email }
    errors { field message code }
  }
}
"""

CHECKOUT_SHIPPING_ADDRESS_UPDATE = """
mutation CheckoutShippingAddressUpdate($id: ID!, $shippingAddress: AddressInput!) {
  checkoutShippingAddressUpdate(id: $id, shippingAddress: $shippingAddress) {
    checkout {
      id
      shippingAddress { firstName lastName city postalCode country { code } }
    }
    errors { field message code }
  }
}
"""

CHECKOUT_BILLING_ADDRESS_UPDATE = """
mutation CheckoutBillingAddressUpdate($id: ID!, $billingAddress: AddressInput!) {
  checkoutBillingAddressUpdate(id: $id, billingAddress: $billingAddress) {
    checkout {
      id
      billingAddress { firstName lastName city postalCode country { code } }
    }
    errors { field message code }
  }
}
"""

CHECKOUT_DELIVERY_METHOD_UPDATE = """
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
"""

CHECKOUT_PAYMENT_CREATE = """
mutation CheckoutPaymentCreate($id: ID!, $input: PaymentInput!) {
  checkoutPaymentCreate(id: $id, input: $input) {
    payment {
      id
      gateway
      total { amount currency }
      chargeStatus
    }
    errors { field message code }
  }
}
"""

CHECKOUT_COMPLETE = """
mutation CheckoutComplete($id: ID!) {
  checkoutComplete(id: $id) {
    order {
      id
      number
      status
      total { gross { amount currency } }
    }
    confirmationNeeded
    confirmationData
    errors { field message code }
  }
}
"""

CHECKOUT_DELETE = """
mutation CheckoutDelete($id: ID!) {
  checkoutDelete(id: $id) {
    errors { field message code }
  }
}
"""

# ============================ 订单 ============================

ORDERS = """
query Orders($first: Int!) {
  orders(first: $first) {
    totalCount
    edges {
      node { id number status total { gross { amount currency } } }
    }
  }
}
"""

ORDER_BY_ID = """
query OrderById($id: ID!) {
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
"""

ORDER_BY_TOKEN = """
query OrderByToken($token: UUID!) {
  orderByToken(token: $token) {
    id
    number
    status
    total { gross { amount currency } }
  }
}
"""

# ============================ 账户与客户 ============================

ACCOUNT_REGISTER = """
mutation AccountRegister($input: AccountRegisterInput!) {
  accountRegister(input: $input) {
    user { id email isActive }
    requiresConfirmation
    errors { field message code }
  }
}
"""

CUSTOMERS = """
query Customers($first: Int!) {
  customers(first: $first) {
    totalCount
    edges { node { id email isActive } }
  }
}
"""

ME = """
query Me {
  me {
    id
    email
    isStaff
    isActive
  }
}
"""

# ============================ 店铺 ============================

SHOP = """
query Shop {
  shop {
    name
    description
    domain { host }
    version
    defaultCountry { code }
    channelCurrencies
  }
}
"""