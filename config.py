# -*- coding: utf-8 -*-
"""全局配置：全部从环境变量读取，默认值仅用于本地开发。

敏感信息（账号、密码）不硬编码，统一走环境变量，模板见 .env.example。
"""
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent

# .env 存在时自动加载；不存在则用默认值
load_dotenv(PROJECT_ROOT / ".env")

# Playwright 默认把浏览器装到用户目录（%LOCALAPPDATA%\ms-playwright），
# 但受限沙箱禁止写入该路径。统一落到项目内的 .playwright-browsers/（已 gitignore），
# 用 setdefault 保证外部显式指定的路径优先。
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(PROJECT_ROOT / ".playwright-browsers"))


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        raise ValueError("环境变量 %s 必须是整数，当前值：%r" % (name, raw))


# ---- 接口 ----
GRAPHQL_URL = os.getenv("SALEOR_GRAPHQL_URL", "http://localhost:8000/graphql/").strip()
TIMEOUT = _get_int("SALEOR_TIMEOUT", 30)
MAX_RESPONSE_MS = _get_int("SALEOR_MAX_RESPONSE_MS", 3000)

# ---- 账号 ----
ADMIN_EMAIL = os.getenv("SALEOR_ADMIN_EMAIL", "admin@example.com").strip()
ADMIN_PASSWORD = os.getenv("SALEOR_ADMIN_PASSWORD", "admin")

# ---- 业务 ----
CHANNEL = os.getenv("SALEOR_CHANNEL", "default-channel").strip()

# ---- UI（Dashboard）----
DASHBOARD_URL = os.getenv("SALEOR_DASHBOARD_URL", "http://localhost:9000").strip()
UI_TIMEOUT_MS = _get_int("SALEOR_UI_TIMEOUT_MS", 15000)
UI_HEADED = os.getenv("SALEOR_UI_HEADED", "0").strip().lower() in {"1", "true", "yes"}

# ---- 日志 ----
LOG_LEVEL = os.getenv("SALEOR_LOG_LEVEL", "INFO").strip().upper()

# ---- 目录 ----
SCHEMA_DIR = PROJECT_ROOT / "schema"
DOCS_DIR = PROJECT_ROOT / "docs"
ALLURE_RESULTS = PROJECT_ROOT / "allure-results"
LOG_DIR = PROJECT_ROOT / "logs"
UI_ARTIFACTS_DIR = PROJECT_ROOT / "ui-artifacts"