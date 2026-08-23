# -*- coding: utf-8 -*-
"""
API 模块初始化

创建主路由并注册所有子路由。
"""

from fastapi import APIRouter

from app.api.routes import (
    health_router,
    chat_router,
    mcp_router,
    a2a_router,
)

# 创建主路由
api_router = APIRouter()

# 注册健康检查路由
api_router.include_router(health_router, tags=["健康检查"])

# 注册统一对话路由（single / multi / master）
api_router.include_router(chat_router, tags=["对话"])

# 注册 MCP 协议代理路由（转发到独立 mcp_server）
api_router.include_router(mcp_router, tags=["MCP 协议代理"])

# 注册 A2A 协议代理路由（转发到独立 a2a_server）
api_router.include_router(a2a_router, tags=["A2A 协议代理"])

__all__ = ["api_router"]
