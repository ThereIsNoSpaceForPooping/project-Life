# -*- coding: utf-8 -*-
"""
核心模块初始化

导出配置和日志工具。
"""

from app.core.config import settings
from app.core.logging import setup_logging, get_logger

__all__ = ["settings", "setup_logging", "get_logger"]
