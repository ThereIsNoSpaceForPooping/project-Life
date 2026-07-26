# -*- coding: utf-8 -*-
"""
日志配置模块

统一日志格式和输出
"""

import logging
import sys

from app.core.config import settings


def setup_logging():
    """初始化日志配置"""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # 日志格式
    fmt = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
    date_fmt = "%Y-%m-%d %H:%M:%S"

    # 配置根日志
    logging.basicConfig(
        level=log_level,
        format=fmt,
        datefmt=date_fmt,
        stream=sys.stdout,
    )

    # 降低第三方库日志级别
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("langchain").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    获取命名日志器

    Args:
        name: 日志器名称，通常用 __name__

    Returns:
        logging.Logger: 配置好的日志器
    """
    return logging.getLogger(name)
