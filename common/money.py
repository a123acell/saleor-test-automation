# -*- coding: utf-8 -*-
"""金额比较工具。

Saleor 返回的金额是 JSON number，被 Python 解析成 float 后会出现
二进制表示误差（如 1.99 变成 1.9899999999999999911182158…）。
直接比较 Decimal(float) 会因上下文精度不同而误判，
因此统一「转字符串 -> 保留两位小数 -> 比较」。
"""
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def money(value) -> Decimal:
    """把金额归一化为保留两位小数的 Decimal。"""
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def money_equal(a, b) -> bool:
    """两位小数精度下比较两个金额是否相等。"""
    return money(a) == money(b)


def money_add(*values) -> Decimal:
    """按两位小数精度求和。"""
    total = Decimal("0.00")
    for value in values:
        total += money(value)
    return total.quantize(CENT, rounding=ROUND_HALF_UP)