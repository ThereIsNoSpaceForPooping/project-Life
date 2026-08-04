# -*- coding: utf-8 -*-
"""
API 模块初始化

创建主路由并注册所有子路由。
"""

from fastapi import APIRouter

from app.api.routes import (
    health_router,
    chat_router,
)

# 创建主路由
api_router = APIRouter()

# 注册健康检查路由
api_router.include_router(health_router, tags=["健康检查"])

# 注册统一对话路由（single / multi / master）
api_router.include_router(chat_router, tags=["对话"])

__all__ = ["api_router"]
