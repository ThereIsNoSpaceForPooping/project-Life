# -*- coding: utf-8 -*-
"""
API 模块初始化

创建主路由并注册所有子路由。
"""

from fastapi import APIRouter

from app.api.routes import (
    health_router,
    chat_router,
    advanced_router,
    mcp_router,
    a2a_router,
    timetravel_router
)

# 创建主路由
api_router = APIRouter()

# 注册健康检查路由
api_router.include_router(health_router, tags=["健康检查"])

# 注册基础对话路由
api_router.include_router(chat_router, tags=["基础对话"])

# 注册高级功能路由
api_router.include_router(advanced_router, prefix="/advanced", tags=["高级功能"])

# 注册 MCP 路由
api_router.include_router(mcp_router, prefix="/mcp", tags=["MCP 协议"])

# 注册 A2A 路由
api_router.include_router(a2a_router, prefix="/a2a", tags=["A2A 协议"])

# 注册时间旅行路由
api_router.include_router(timetravel_router, prefix="/timetravel", tags=["时间旅行"])

__all__ = ["api_router"]
