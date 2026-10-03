# -*- coding: utf-8 -*-
"""汇总 JMeter JTL 结果，输出 Markdown 统计表（供性能报告引用）。

用法：
    python perftests/analyze_results.py                      # 默认读 perftests/results
    python perftests/analyze_results.py --dir <结果目录> --out <输出 md>

只依赖标准库，不引入新依赖（自检第 13 项会校验）。
文件名形如 grad-5.jtl / grad-10.jtl，其中的数字作为并发档位。
"""
import argparse
import csv
import io
import math
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DIR = os.path.join(ROOT, "perftests", "results")

_LEVEL_RE = re.compile(r"grad-(\d+)\.jtl$", re.IGNORECASE)

# 只统计真实请求，排除 setUp / tearDown 的辅助采样
_SETUP_LABELS = ("SETUP ",)
_TEARDOWN_LABELS = ("清理残留 checkout",)


def _percentile(sorted_values, pct):
    """线性插值分位数，n=1 时直接返回该值。"""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    pos = (len(sorted_values) - 1) * pct / 100.0
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return float(sorted_values[lo])
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo)


def _load(path):
    rows = []
    with io.open(path, "r", encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            try:
                elapsed = float(row["elapsed"])
            except (KeyError, TypeError, ValueError):
                continue
            rows.append({
                "ts": int(row["timeStamp"]),
                "elapsed": elapsed,
                "label": row["label"],
                "code": row.get("responseCode", ""),
                "success": str(row.get("success", "")).strip().lower() == "true",
                "message": (row.get("failureMessage") or "").replace("\n", " ").strip(),
            })
    return rows


def _is_aux(label):
    return label.startswith(_SETUP_LABELS) or label.startswith(_TEARDOWN_LABELS)


def _aggregate(rows):
    """按 label 聚合，返回 {label: metrics}。"""
    groups = {}
    for r in rows:
        groups.setdefault(r["label"], []).append(r)

    out = {}
    for label, items in groups.items():
        times = sorted(i["elapsed"] for i in items)
        ok = sum(1 for i in items if i["success"])
        span = max(i["ts"] + i["elapsed"] for i in items) - min(i["ts"] for i in items)
        out[label] = {
            "samples": len(items),
            "ok": ok,
            "errors": len(items) - ok,
            "err_rate": (len(items) - ok) / len(items) * 100.0 if items else 0.0,
            "avg": sum(times) / len(times),
            "min": times[0],
            "max": times[-1],
            "p50": _percentile(times, 50),
            "p90": _percentile(times, 90),
            "p95": _percentile(times, 95),
            "p99": _percentile(times, 99),
            "tps": len(items) / (span / 1000.0) if span > 0 else 0.0,
        }
    return out


def _fmt(ms):
    return "%.0f" % ms


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=DEFAULT_DIR, help="JTL 结果目录")
    ap.add_argument("--out", default=None, help="输出 Markdown 路径（默认打印到 stdout）")
    args = ap.parse_args()

    if not os.path.isdir(args.dir):
        print("结果目录不存在：%s" % args.dir)
        return 1

    levels = []
    for name in sorted(os.listdir(args.dir)):
        m = _LEVEL_RE.search(name)
        if m:
            levels.append((int(m.group(1)), os.path.join(args.dir, name)))
    levels.sort()
    if not levels:
        print("未在 %s 找到 grad-<并发>.jtl" % args.dir)
        return 1

    lines = []
    lines.append("### 各并发档位汇总\n")
    lines.append("| 并发 | 采样数 | 平均(ms) | p90(ms) | p95(ms) | p99(ms) | 最大(ms) | 错误率 | 吞吐(/s) |")
    lines.append("| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")

    detail_blocks = []
    for level, path in levels:
        rows = _load(path)
        biz = [r for r in rows if not _is_aux(r["label"])]
        agg = _aggregate(biz)
        total = len(biz)
        errs = sum(v["errors"] for v in agg.values())
        span = (max(r["ts"] + r["elapsed"] for r in biz) - min(r["ts"] for r in biz)) if biz else 0
        tps = total / (span / 1000.0) if span > 0 else 0.0
        times = sorted(r["elapsed"] for r in biz)
        lines.append("| %d | %d | %s | %s | %s | %s | %s | %.2f%% | %.1f |" % (
            level, total,
            _fmt(sum(times) / len(times)) if times else "0",
            _fmt(_percentile(times, 90)), _fmt(_percentile(times, 95)),
            _fmt(_percentile(times, 99)), _fmt(times[-1]) if times else "0",
            errs / total * 100.0 if total else 0.0, tps,
        ))

        block = ["#### 并发 %d — 分接口明细\n" % level]
        block.append("| 接口 | 采样 | 平均(ms) | p95(ms) | 最大(ms) | 错误 | 错误率 |")
        block.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
        for label in sorted(agg, key=lambda k: -agg[k]["samples"]):
            v = agg[label]
            block.append("| %s | %d | %s | %s | %s | %d | %.2f%% |" % (
                label, v["samples"], _fmt(v["avg"]), _fmt(v["p95"]), _fmt(v["max"]),
                v["errors"], v["err_rate"],
            ))
        fails = {}
        for r in biz:
            if not r["success"]:
                fails.setdefault((r["label"], r["code"], r["message"][:120]), 0)
                fails[(r["label"], r["code"], r["message"][:120])] += 1
        if fails:
            block.append("\n**失败明细**\n")
            block.append("| 接口 | 状态码 | 信息 | 次数 |")
            block.append("| --- | --- | --- | ---: |")
            for (label, code, msg), cnt in sorted(fails.items(), key=lambda kv: -kv[1]):
                block.append("| %s | %s | %s | %d |" % (label, code, msg or "-", cnt))
        detail_blocks.append("\n".join(block))

    lines.append("")
    lines.extend(detail_blocks)

    text = "\n".join(lines) + "\n"
    if args.out:
        with io.open(args.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print("已写出：%s（%d 个并发档位）" % (args.out, len(levels)))
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())