# -*- coding: utf-8 -*-
"""N+1 查询探测：用 Postgres SQL 日志统计一次 GraphQL 请求的真实 SELECT 次数。

原理：临时打开 log_statement=all，分别统计「空闲窗口」与「请求窗口」的
SELECT 语句数，差值即该请求在数据库侧触发的查询次数。对不同页大小重复测量：

- 查询次数不随页大小增长 -> DataLoader 批量加载生效，无 N+1
- 查询次数随页大小线性增长 -> 存在 N+1，需按字段定位

用法：python scripts/query_count_probe.py
前置：本地 saleor-platform 的 Docker Compose 正在运行；依赖 requests。
测量结束后自动恢复 log_statement 配置，不在数据库留下残留。

背景：GraphQL 的列表接口天然容易 N+1——每行再嵌套查询子对象（如 variants、
pricing）时，ORM 若逐行取数，SQL 次数会随行数线性增长。Saleor 3.x 内部用
DataLoader 做批量加载，本脚本用于实测验证而非凭文档推断。
"""
import os
import subprocess
import sys
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

DB_CONTAINER = os.getenv("SALEOR_DB_CONTAINER", "saleor-platform-main-db-1")
DB_USER = os.getenv("SALEOR_DB_USER", "saleor")
DB_NAME = os.getenv("SALEOR_DB_NAME", "saleor")
GRAPHQL_URL = os.getenv("SALEOR_GRAPHQL_URL", "http://localhost:8000/graphql/")
CHANNEL = os.getenv("SALEOR_CHANNEL", "default-channel")

# 典型 N+1 高危形态：列表 + 每行嵌套子对象（variants）+ 孙对象（pricing）
PRODUCTS_WITH_VARIANTS = """
query($c: String!, $first: Int!) {
  products(first: $first, channel: $c) {
    totalCount
    edges {
      node {
        id
        name
        variants { name pricing { price { gross { amount } } } }
      }
    }
  }
}
"""


def _docker(*args):
    return subprocess.run(["docker", *args], check=True, capture_output=True, text=True)


def _psql(sql):
    _docker("exec", DB_CONTAINER, "psql", "-U", DB_USER, "-d", DB_NAME, "-c", sql)


def _select_count_since(epoch):
    """统计容器自某时刻起记录的 SELECT 语句数。

    Postgres 每条语句产生一行 `... LOG:  statement: SELECT ...`，
    语句内的换行只会成为后续物理行，不再含 statement: 前缀，可安全按行计数。
    """
    out = _docker("logs", "--since", str(int(epoch)), DB_CONTAINER).stderr
    return sum(1 for line in out.splitlines() if "statement: SELECT" in line)


def enable_sql_log():
    _psql("ALTER SYSTEM SET log_statement = 'all';")
    _psql("SELECT pg_reload_conf();")


def disable_sql_log():
    _psql("ALTER SYSTEM RESET log_statement;")
    _psql("SELECT pg_reload_conf();")


def run_products(first):
    """发送一次商品列表查询，返回本次返回的商品数。"""
    resp = requests.post(
        GRAPHQL_URL,
        json={
            "query": PRODUCTS_WITH_VARIANTS,
            "variables": {"c": CHANNEL, "first": first},
        },
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()
    assert not payload.get("errors"), payload["errors"]
    return len(payload["data"]["products"]["edges"])


def measure(label, fn, idle_per_sec):
    """在独立时间窗内执行 fn，统计扣除空闲噪声后的 SELECT 次数。"""
    start = time.time()
    extra = fn()
    time.sleep(1.0)  # 等待窗口内最后一条日志落盘
    elapsed = time.time() - start
    raw = _select_count_since(start)
    noise = round(idle_per_sec * elapsed)
    return {"label": label, "raw": raw, "noise": noise, "net": raw - noise, "edges": extra}


def main():
    print("打开 SQL 日志（log_statement=all）…")
    enable_sql_log()
    try:
        time.sleep(1.0)
        mark = time.time()
        time.sleep(3.0)
        idle = _select_count_since(mark)
        idle_per_sec = idle / 3.0
        print("空闲基线：%d 次 SELECT / 3s（%.2f 次/s）" % (idle, idle_per_sec))
        print()

        rows = [
            measure("products first=5（含 variants+pricing）", lambda: run_products(5), idle_per_sec),
            measure("products first=25（含 variants+pricing）", lambda: run_products(25), idle_per_sec),
            measure("products first=100（含 variants+pricing）", lambda: run_products(100), idle_per_sec),
        ]

        print("%-40s %8s %8s %8s" % ("场景", "原始", "扣空闲", "净查询"))
        for r in rows:
            print("%-40s %8d %8d %8d" % (r["label"], r["raw"], r["noise"], r["net"]))
        print()
        print("返回商品数：%s" % [r["edges"] for r in rows])
        print("净 SELECT 次数：%s" % [r["net"] for r in rows])

        growth = rows[-1]["net"] - rows[0]["net"]
        print("页大小 5 -> 100 的查询次数增量：%d" % growth)
        threshold = max(2, rows[0]["net"] // 5)
        if growth <= threshold:
            print("结论：查询次数基本不随页大小增长，DataLoader 批量加载生效，未复现 N+1。")
        else:
            print("结论：查询次数随页大小线性增长，疑似 N+1，需按嵌套字段逐个定位。")
    finally:
        print()
        print("恢复 SQL 日志配置（log_statement 重置）…")
        disable_sql_log()


if __name__ == "__main__":
    main()
