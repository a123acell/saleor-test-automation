# -*- coding: utf-8 -*-
"""数据驱动支撑：加载用例数据文件并解析变量占位符。

数据文件放在 data/ 目录，用例只描述「调哪个语句、传什么变量、断言什么」，
不写 Python 逻辑，便于非开发同学维护与评审。
"""
import json
import time
from pathlib import Path
from typing import Any, Dict, List

import config

DATA_DIR = config.PROJECT_ROOT / "data"


def load_cases(filename: str) -> List[Dict[str, Any]]:
    path = DATA_DIR / filename
    if not path.exists():
        raise FileNotFoundError("用例数据文件不存在：%s" % path)
    with open(path, "r", encoding="utf-8") as f:
        cases = json.load(f)
    if not isinstance(cases, list):
        raise ValueError("用例数据文件应为数组：%s" % path)
    return cases


def build_context(admin_email: str, admin_password: str, channel: str, variant_id: str) -> Dict[str, Any]:
    """构造变量占位符的取值表。"""
    return {
        "ADMIN_EMAIL": admin_email,
        "ADMIN_PASSWORD": admin_password,
        "CHANNEL": channel,
        "VARIANT_ID": variant_id,
        "UNIQUE_EMAIL": "autotest%d@example.com" % int(time.time() * 1000),
    }


def _resolve(value: Any, ctx: Dict[str, Any]) -> Any:
    if isinstance(value, str) and value.startswith("$"):
        key = value[1:]
        if key not in ctx:
            raise KeyError("未定义的变量占位符：%s（可用：%s）" % (value, sorted(ctx)))
        return ctx[key]
    if isinstance(value, dict):
        return {k: _resolve(v, ctx) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve(v, ctx) for v in value]
    return value


def resolve_variables(variables: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    return _resolve(variables or {}, ctx)