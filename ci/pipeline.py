# -*- coding: utf-8 -*-
"""CI 阶段注册表与执行器 —— Jenkins 与本地演练共用同一入口。

为什么要有这一层：
如果 Jenkinsfile 直接内联测试命令，本地想验证流水线就得手抄一遍命令，
两处必然漂移——改了脚本忘了改 Jenkinsfile，CI 会静默地跑旧命令。
因此 Jenkinsfile 只负责编排（agent / 参数 / when / post 归档），
具体命令统一走 `python ci/pipeline.py <stage>`；本地 `python ci/pipeline.py all`
即可把整条流水线完整跑一遍。

Jenkinsfile 中出现的阶段与这里的 STAGES 是否一致，由 scripts/selfcheck.py 第 18 项机械校验。
"""
import argparse
import csv
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config  # noqa: E402  # 触发 .env 加载与 PLAYWRIGHT_BROWSERS_PATH 设置

PY = sys.executable
ALLURE_DIR = ROOT / "allure-results"
REPORTS_DIR = ROOT / "reports"
PERF_CI_DIR = ROOT / "perftests" / "results" / "ci"
JMX = ROOT / "perftests" / "saleor-perf.jmx"
PERF_PROPS = ROOT / "perftests" / "perf.properties"

# 阶段注册表：Jenkinsfile 的每个 stage 都调用这里的 id。
# needs_service=True 表示该阶段需要被测服务在线，离线环境会明确失败而不是静默跳过。
STAGES = [
    {"id": "bootstrap", "name": "环境与依赖检查", "needs_service": False},
    {"id": "selfcheck", "name": "工程自检", "needs_service": False},
    {"id": "collect", "name": "用例收集", "needs_service": False},
    {"id": "api", "name": "接口自动化", "needs_service": True},
    {"id": "ui", "name": "UI 自动化", "needs_service": True},
    {"id": "perf", "name": "性能冒烟", "needs_service": True},
]

STAGE_IDS = [s["id"] for s in STAGES]


class StageError(RuntimeError):
    """阶段失败。"""


def _stage(stage_id):
    for s in STAGES:
        if s["id"] == stage_id:
            return s
    raise StageError("未注册的阶段 id：%s" % stage_id)


def _run(cmd, cwd=ROOT):
    """执行命令，实时透传输出；返回退出码。"""
    print("$ %s" % " ".join(str(c) for c in cmd), flush=True)
    proc = subprocess.run([str(c) for c in cmd], cwd=str(cwd))
    return proc.returncode


def _must(cmd, label):
    code = _run(cmd)
    if code != 0:
        raise StageError("%s 失败（退出码 %d）" % (label, code))


def _url_alive(url):
    try:
        urllib.request.urlopen(url, timeout=5)
        return True
    except (urllib.error.URLError, OSError):
        return False


def _service_alive():
    return _url_alive(config.GRAPHQL_URL)


def _jmeter_bin():
    # JMETER_HOME 是 JMeter 安装时设置的标准变量，未加入 PATH 时靠它定位
    home = os.getenv("JMETER_HOME")
    candidates = [
        os.getenv("JMETER_BIN"),
        shutil.which("jmeter"),
        os.path.join(home, "bin", "jmeter.bat") if home else None,
        os.path.join(home, "bin", "jmeter") if home else None,
    ]
    for cand in candidates:
        if cand and Path(cand).exists():
            return cand
    return None


def _allure_bin():
    for cand in (os.getenv("ALLURE_BIN"), shutil.which("allure")):
        if cand and Path(cand).exists():
            return cand
    return None


# ---------------- 各阶段实现 ----------------


def stage_bootstrap():
    """检查运行环境。缺依赖直接失败，缺可选工具只告警。"""
    problems = []
    if sys.version_info < (3, 9):
        problems.append("Python 版本过低：%s（需 >= 3.9）" % sys.version.split()[0])

    for mod in ("pytest", "requests", "allure", "dotenv", "graphql", "playwright"):
        try:
            __import__(mod)
        except ImportError:
            problems.append("缺少依赖：%s（执行 pip install -r requirements.txt）" % mod)

    browsers = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", ""))
    if not browsers.is_dir():
        problems.append("Playwright 浏览器目录不存在：%s（执行 playwright install chromium）" % browsers)

    if problems:
        raise StageError("；".join(problems))

    jmeter = _jmeter_bin()
    allure = _allure_bin()
    print("Python %s" % sys.version.split()[0])
    print("pytest %s" % __import__("pytest").__version__)
    print("被测接口：%s（%s）" % (config.GRAPHQL_URL, "在线" if _service_alive() else "离线"))
    print("Dashboard：%s" % config.DASHBOARD_URL)
    print("Playwright 浏览器：%s" % browsers)
    print("JMeter：%s" % (jmeter or "未找到（性能阶段需要，可设 JMETER_BIN）"))
    print("Allure CLI：%s" % (allure or "未找到（Jenkins 用 Allure 插件渲染 allure-results，可不装）"))
    return "依赖齐全，%s" % ("被测服务在线" if _service_alive() else "被测服务离线")


def stage_selfcheck():
    _must([PY, "scripts/selfcheck.py"], "工程自检")
    return "自检全部通过"


def stage_collect():
    """离线确认用例可被 pytest 正确发现（不依赖被测服务）。"""
    code = _run([PY, "-m", "pytest", "--collect-only", "-q", "testcases", "uitests"])
    if code != 0:
        raise StageError("用例收集失败（退出码 %d）" % code)
    return "用例可正常收集"


def stage_api():
    ALLURE_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    # 清掉上一轮的 Allure 原始数据，避免历史结果混进本次报告
    for old in ALLURE_DIR.glob("*.json"):
        old.unlink()
    _must(
        [PY, "-m", "pytest", "testcases",
         "--alluredir=%s" % ALLURE_DIR, "--junitxml=%s" % (REPORTS_DIR / "junit-api.xml")],
        "接口自动化",
    )
    return "接口用例全部通过"


def stage_ui():
    # Dashboard 离线时 uitests 会整组 skip，pytest 退出码仍为 0——那是假通过。
    # 这里显式失败，让「UI 阶段通过」意味着用例真的跑过。
    if not _url_alive(config.DASHBOARD_URL):
        raise StageError("Dashboard 不可达：%s（UI 用例会被整组跳过，按失败处理）" % config.DASHBOARD_URL)
    ALLURE_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    _must(
        [PY, "-m", "pytest", "uitests", "-m", "ui_smoke",
         "--alluredir=%s" % ALLURE_DIR, "--junitxml=%s" % (REPORTS_DIR / "junit-ui.xml")],
        "UI 自动化",
    )
    return "UI 冒烟用例全部通过"


def stage_perf():
    """性能冒烟：单档短时压测 + 结果汇总 + 失败率闸门。

    这里只跑短时单档用于验证链路与清理机制；容量评估用 perftests/README.md 里的梯度加压。
    """
    jmeter = _jmeter_bin()
    if not jmeter:
        raise StageError("未找到 JMeter，请安装或设置 JMETER_BIN 环境变量")

    threads = os.getenv("PERF_THREADS", "5")
    duration = os.getenv("PERF_DURATION", "15")
    PERF_CI_DIR.mkdir(parents=True, exist_ok=True)
    jtl = PERF_CI_DIR / ("grad-%s.jtl" % threads)
    if jtl.exists():
        jtl.unlink()

    _must(
        [jmeter, "-n", "-t", JMX, "-q", PERF_PROPS,
         "-Jthreads=%s" % threads, "-Jrampup=2", "-Jduration=%s" % duration,
         "-l", jtl],
        "性能压测",
    )

    with jtl.open(encoding="utf-8", errors="replace") as f:
        rows = [r for r in csv.DictReader(f) if r.get("elapsed")]
    if not rows:
        raise StageError("压测未产生任何采样，请检查计划与参数")

    failed = [r for r in rows if str(r.get("success", "")).strip().lower() != "true"]
    _run([PY, "perftests/analyze_results.py", "--dir", PERF_CI_DIR])

    cleanup = [r for r in rows if r["label"].startswith("清理残留")]
    if cleanup:
        print("tearDown：%s" % cleanup[-1].get("responseMessage", ""))

    if failed:
        detail = "; ".join("%s → %s" % (r["label"], r.get("responseMessage", "")) for r in failed[:5])
        raise StageError("压测出现 %d 个失败采样：%s" % (len(failed), detail))
    return "%s 采样、0 失败（%s 并发 / %ss）" % (len(rows), threads, duration)


_RUNNERS = {
    "bootstrap": stage_bootstrap,
    "selfcheck": stage_selfcheck,
    "collect": stage_collect,
    "api": stage_api,
    "ui": stage_ui,
    "perf": stage_perf,
}


def run_one(stage_id):
    """执行单个阶段，返回 (是否成功, 说明)。"""
    meta = _stage(stage_id)
    print("\n" + "=" * 66)
    print("[阶段] %s（%s）" % (meta["name"], stage_id))
    print("=" * 66)
    if meta["needs_service"] and not _service_alive():
        return False, "被测服务不可达：%s" % config.GRAPHQL_URL
    started = time.time()
    try:
        detail = _RUNNERS[stage_id]() or "完成"
    except StageError as exc:
        return False, str(exc)
    except Exception as exc:  # noqa: BLE001
        return False, "执行异常：%s: %s" % (type(exc).__name__, exc)
    return True, "%s（%.1fs）" % (detail, time.time() - started)


def main():
    ap = argparse.ArgumentParser(description="Saleor 测试工程 CI 阶段执行器")
    ap.add_argument("stage", nargs="?", default="all",
                    help="阶段 id，或 all 依次执行全部阶段；用 --list 查看")
    ap.add_argument("--list", action="store_true", help="列出所有阶段")
    args = ap.parse_args()

    if args.list:
        for s in STAGES:
            print("%-10s %-16s %s" % (s["id"], s["name"],
                                      "需要被测服务" if s["needs_service"] else "离线可跑"))
        return 0

    targets = STAGE_IDS if args.stage == "all" else [args.stage]
    unknown = [t for t in targets if t not in STAGE_IDS]
    if unknown:
        print("未注册的阶段：%s（可用：%s）" % (unknown, ", ".join(STAGE_IDS)))
        return 2

    print("=" * 66)
    print("Saleor 测试工程 CI 流水线 · 共 %d 个阶段" % len(targets))
    print("=" * 66)

    results = []
    for stage_id in targets:
        ok, detail = run_one(stage_id)
        results.append((stage_id, ok, detail))
        if not ok and args.stage == "all":
            print("\n阶段 %s 失败，中止后续阶段（避免在坏环境上继续消耗时间）" % stage_id)
            break

    print("\n" + "=" * 66)
    print("阶段结果")
    print("=" * 66)
    for stage_id, ok, detail in results:
        print("[%s] %-10s %s" % ("PASS" if ok else "FAIL", stage_id, detail))
    failed = [r for r in results if not r[1]]
    print("-" * 66)
    print("共 %d 个阶段，通过 %d，失败 %d" % (len(results), len(results) - len(failed), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())