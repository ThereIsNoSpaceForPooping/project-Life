# -*- coding: utf-8 -*-
"""
路由模块初始化

核心路由：
- health: 健康检查
- chat: 统一对话入口（single / multi / master）

外部协议路由：
- mcp: MCP 协议代理（转发到独立 mcp_server）
- a2a: A2A 协议代理（转发到独立 a2a_server）
"""

from app.api.routes.health import router as health_router
from app.api.routes.chat import router as chat_router
from app.api.routes.mcp import router as mcp_router
from app.api.routes.a2a import router as a2a_router

__all__ = [
    "health_router",
    "chat_router",
    "mcp_router",
    "a2a_router",
]
