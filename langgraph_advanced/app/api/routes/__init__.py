# -*- coding: utf-8 -*-
"""
路由模块初始化

只保留核心路由：
- health: 健康检查
- chat: 统一对话入口（single / multi / master）

MCP、A2A、时间旅行等高级功能已集成到 master_graph 中，
通过 POST /chat?mode=master 统一访问。
"""

from app.api.routes.health import router as health_router
from app.api.routes.chat import router as chat_router

__all__ = [
    "health_router",
    "chat_router",
]
