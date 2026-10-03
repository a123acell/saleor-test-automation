# -*- coding: utf-8 -*-
"""分级日志：控制台输出，可选写入文件。"""
import logging
import sys

from config import LOG_DIR, LOG_LEVEL

_CONFIGURED = set()


def get_logger(name: str = "saleor") -> logging.Logger:
    logger = logging.getLogger(name)
    if name in _CONFIGURED:
        return logger

    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    logger.propagate = False

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-7s] %(message)s",
        datefmt="%H:%M:%S",
    )

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    logger.addHandler(console)

    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(LOG_DIR / "run.log", encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        # 日志目录不可写时不阻断测试执行
        pass

    _CONFIGURED.add(name)
    return logger