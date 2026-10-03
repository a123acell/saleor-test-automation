# -*- coding: utf-8 -*-
"""校验 Apifox 集合：按顺序真实执行集合中的每个请求。

目的：确保导出给 Apifox 的集合不是「看起来对」，而是每个请求都实测可用。
依赖本地 Saleor 已启动并已 populatedb。
"""
import json
import os
import re
import sys
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COLLECTION = os.path.join(ROOT, "apifox", "saleor-graphql.postman_collection.json")

VAR_RE = re.compile(r"\{\{(\w+)\}\}")
S = requests.Session()


def substitute(obj, variables):
    if isinstance(obj, str):
        return VAR_RE.sub(lambda m: str(variables.get(m.group(1), m.group(0))), obj)
    if isinstance(obj, dict):
        return {k: substitute(v, variables) for k, v in obj.items()}
    if isinstance(obj, list):
        return [substitute(v, variables) for v in obj]
    return obj


def save_token(j, v):
    r = j["data"]["tokenCreate"]
    v["token"] = r["token"]
    if r.get("refreshToken"):
        v["refreshToken"] = r["refreshToken"]


def save_variant(j, v):
    v["variantId"] = j["data"]["products"]["edges"][0]["node"]["variants"][0]["id"]


def save_checkout(j, v):
    c = j["data"]["checkoutCreate"]["checkout"]
    v["checkoutId"] = c["id"]
    v["checkoutToken"] = c["token"]
    v["checkoutTotal"] = c["totalPrice"]["gross"]["amount"]


def save_checkout_detail(j, v):
    c = j["data"]["checkout"]
    v["checkoutTotal"] = c["totalPrice"]["gross"]["amount"]
    if c["lines"]:
        v["lineId"] = c["lines"][0]["id"]
    if c["availableShippingMethods"]:
        v["shippingMethodId"] = c["availableShippingMethods"][0]["id"]


def save_total_after_delivery(j, v):
    v["checkoutTotal"] = j["data"]["checkoutDeliveryMethodUpdate"]["checkout"]["totalPrice"]["gross"]["amount"]


def save_order(j, v):
    o = j["data"]["checkoutComplete"]["order"]
    if o:
        v["orderId"] = o["id"]


EXTRACTORS = {
    "01 登录获取 Token": save_token,
    "05 商品列表（分页）": save_variant,
    "07 创建购物车（加购）": save_checkout,
    "08 查询购物车详情": save_checkout_detail,
    "10 查询购物车详情（取配送方式）": save_checkout_detail,
    "11 选择配送方式": save_total_after_delivery,
    "13 完成下单": save_order,
}

EXTENSION_FOLDER = "06 购物车扩展操作"


def make_fresh_checkout(v):
    """为扩展操作新建一个购物车，避免复用已下单的购物车。"""
    q = ('mutation($in:CheckoutCreateInput!){checkoutCreate(input:$in){checkout{id token '
         'totalPrice{gross{amount}} lines{id}} errors{field message code}}}')
    body = {"query": q, "variables": {"in": {"channel": "default-channel", "email": "buyer@example.com",
                                             "lines": [{"quantity": 1, "variantId": v["variantId"]}]}}}
    r = S.post(v["baseUrl"] + "/graphql/", json=body,
               headers={"Authorization": "Bearer " + v["token"]}, timeout=60).json()
    c = r["data"]["checkoutCreate"]["checkout"]
    v["checkoutId"] = c["id"]
    v["lineId"] = c["lines"][0]["id"]
    v["checkoutTotal"] = c["totalPrice"]["gross"]["amount"]


def main():
    with open(COLLECTION, encoding="utf-8") as f:
        coll = json.load(f)

    variables = {x["key"]: x["value"] for x in coll["variable"]}

    passed, failed = [], []
    idx = 0
    total = sum(len(fo["item"]) for fo in coll["item"])

    for fo in coll["item"]:
        print("\n[%s]" % fo["name"])
        for item in fo["item"]:
            idx += 1
            name = item["name"]

            if fo["name"] == EXTENSION_FOLDER and name == "18 修改商品数量":
                make_fresh_checkout(variables)
                print("     (已为扩展操作新建购物车)")

            # 预请求脚本：随机邮箱
            if name == "17 账户注册":
                variables["registerEmail"] = "autotest_%d@example.com" % int(time.time() * 1000)

            req = item["request"]
            url = substitute(req["url"]["raw"], variables)
            headers = {h["key"]: substitute(h["value"], variables) for h in req["header"]}
            body = {
                "query": req["body"]["graphql"]["query"],
                "variables": json.loads(substitute(req["body"]["graphql"]["variables"], variables)),
            }

            t0 = time.time()
            try:
                resp = S.post(url, json=body, headers=headers, timeout=60)
                ms = (time.time() - t0) * 1000
                payload = resp.json()
            except Exception as exc:
                failed.append((name, "请求异常: %s" % exc))
                print("  [%2d/%d] %-22s 请求异常: %s" % (idx, total, name, exc))
                continue

            gql_errors = payload.get("errors")
            data = payload.get("data") or {}
            biz_errors = None
            for val in data.values():
                if isinstance(val, dict) and isinstance(val.get("errors"), list) and val["errors"]:
                    biz_errors = val["errors"]

            if resp.status_code != 200 or gql_errors:
                detail = json.dumps(gql_errors or payload, ensure_ascii=False)[:180]
                failed.append((name, detail))
                print("  [%2d/%d] %-22s 失败 HTTP %s | %s" % (idx, total, name, resp.status_code, detail))
                continue

            if biz_errors:
                failed.append((name, json.dumps(biz_errors, ensure_ascii=False)[:180]))
                print("  [%2d/%d] %-22s 业务错误 | %s" % (idx, total, name, json.dumps(biz_errors, ensure_ascii=False)[:140]))
                continue

            ext = EXTRACTORS.get(name)
            if ext:
                ext(payload, variables)

            passed.append(name)
            print("  [%2d/%d] %-22s OK  %dms" % (idx, total, name, ms))

    print("\n" + "=" * 56)
    print("通过 %d / %d" % (len(passed), total))
    if failed:
        print("失败 %d 个：" % len(failed))
        for n, d in failed:
            print("  - %s : %s" % (n, d))
    print("=" * 56)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())