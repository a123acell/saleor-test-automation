# -*- coding: utf-8 -*-
"""从内省结果生成 Saleor 接口清单（按业务模块归类）。

输入：schema/saleor_schema.json
输出：docs/接口清单.md
"""
import json
import os
import re
from collections import OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_JSON = os.path.join(ROOT, "schema", "saleor_schema.json")
OUT_MD = os.path.join(ROOT, "docs", "接口清单.md")

# 归类规则：按顺序匹配，先命中先归类
RULES = [
    ("鉴权与令牌", r"^(token|verifyToken|createToken|refreshToken|deactivateAllUserTokens|externalObtainAccessTokens|externalRefresh|externalVerify)"),
    ("购物车与结算", r"^checkout"),
    ("订单", r"^(order|draftOrder|orderSettings)"),
    ("支付与交易", r"^(payment|transaction|storedPaymentMethod)"),
    ("配送与运费", r"^(shipping|delivery|shippingZone|shippingMethod|shippingPrice)"),
    ("促销与折扣", r"^(discount|promotion|voucher|sale)"),
    ("礼品卡与发票", r"^(giftCard|invoice)"),
    ("商品与目录", r"^(product|category|collection|attribute|digitalContent|variant)"),
    ("库存与仓库", r"^(warehouse|stock|allocation)"),
    ("账户与客户", r"^(account|user|customer|password|setPassword|requestPassword|staff|permission)"),
    ("渠道", r"^channel"),
    ("店铺与税务", r"^(shop|tax|taxClass|settings)"),
    ("应用与集成", r"^(app|webhook|extension|event|observability)"),
    ("页面与菜单", r"^(page|menu|translation|language)"),
    ("组织与团队", r"^(group|team)"),
    ("导出任务", r"^export"),
]


def type_ref(t):
    """把 __Type 引用渲染成 GraphQL 写法，如 [String!]!"""
    if t is None:
        return "?"
    kind = t.get("kind")
    name = t.get("name")
    if kind == "NON_NULL":
        return type_ref(t.get("ofType")) + "!"
    if kind == "LIST":
        return "[" + type_ref(t.get("ofType")) + "]"
    return name or "?"


def load_fields(schema):
    types = schema["types"]
    qname = schema["queryType"]["name"]
    mname = schema["mutationType"]["name"]
    q = next((t for t in types if t["name"] == qname), None)
    m = next((t for t in types if t["name"] == mname), None)
    return (q or {}).get("fields") or [], (m or {}).get("fields") or []


def categorize(name):
    for label, pattern in RULES:
        if re.match(pattern, name):
            return label
    return "其他"


def summarize_args(field, limit=4):
    args = field.get("args") or []
    if not args:
        return "—"
    parts = []
    for a in args[:limit]:
        parts.append("%s: %s" % (a["name"], type_ref(a["type"])))
    if len(args) > limit:
        parts.append("…(+%d)" % (len(args) - limit))
    return ", ".join(parts)


def main():
    with open(SCHEMA_JSON, encoding="utf-8") as f:
        schema = json.load(f)["data"]["__schema"]

    queries, mutations = load_fields(schema)

    groups = OrderedDict()
    for kind, fields in (("Query", queries), ("Mutation", mutations)):
        for fld in fields:
            label = categorize(fld["name"])
            groups.setdefault(label, {"Query": [], "Mutation": []})
            groups[label][kind].append(fld)

    order = [label for label, _ in RULES] + ["其他"]
    groups = OrderedDict((k, groups[k]) for k in order if k in groups)

    lines = []
    lines.append("# Saleor GraphQL 接口清单\n")
    lines.append("> 来源：本地 Saleor 3.23.34 实例内省（`%s`）  " % schema.get("__endpoint", "http://localhost:8000/graphql/"))
    lines.append("> 生成方式：`scripts/fetch_schema.py` + `scripts/build_api_inventory.py`，可重复执行  ")
    lines.append("> 全量规模：**%d 个 Query + %d 个 Mutation = %d 个操作**\n" % (len(queries), len(mutations), len(queries) + len(mutations)))

    lines.append("## 一、模块总览\n")
    lines.append("| 模块 | Query | Mutation | 合计 |")
    lines.append("| --- | ---: | ---: | ---: |")
    for label, g in groups.items():
        lines.append("| %s | %d | %d | %d |" % (label, len(g["Query"]), len(g["Mutation"]), len(g["Query"]) + len(g["Mutation"])))
    lines.append("| **合计** | **%d** | **%d** | **%d** |\n" % (len(queries), len(mutations), len(queries) + len(mutations)))

    lines.append("## 二、明细\n")
    for label, g in groups.items():
        total = len(g["Query"]) + len(g["Mutation"])
        lines.append("### %s（%d）\n" % (label, total))
        if g["Query"]:
            lines.append("**Query（%d）**\n" % len(g["Query"]))
            lines.append("| 操作名 | 主要入参 |")
            lines.append("| --- | --- |")
            for fld in g["Query"]:
                lines.append("| `%s` | %s |" % (fld["name"], summarize_args(fld)))
            lines.append("")
        if g["Mutation"]:
            lines.append("**Mutation（%d）**\n" % len(g["Mutation"]))
            lines.append("| 操作名 | 主要入参 |")
            lines.append("| --- | --- |")
            for fld in g["Mutation"]:
                lines.append("| `%s` | %s |" % (fld["name"], summarize_args(fld)))
            lines.append("")

    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print("模块统计：")
    for label, g in groups.items():
        print("  %-12s Query %3d | Mutation %3d" % (label, len(g["Query"]), len(g["Mutation"])))
    print("\n输出：%s" % OUT_MD)


if __name__ == "__main__":
    main()