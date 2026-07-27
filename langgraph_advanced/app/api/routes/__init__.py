# -*- coding: utf-8 -*-
"""
路由模块初始化

导出所有路由模块。
"""

from app.api.routes.health import router as health_router
from app.api.routes.chat import router as chat_router
from app.api.routes.advanced import router as advanced_router
from app.api.routes.mcp import router as mcp_router
from app.api.routes.a2a import router as a2a_router
from app.api.routes.timetravel import router as timetravel_router

__all__ = [
    "health_router",
    "chat_router",
    "advanced_router",
    "mcp_router",
    "a2a_router",
    "timetravel_router",
]
