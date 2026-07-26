# -*- coding: utf-8 -*-
"""
FastAPI Demo - API 路由模块
"""

from fastapi import APIRouter

from app.api.routes import user_router, health_router

# 主路由
api_router = APIRouter()

# 注册子路由
api_router.include_router(health_router, tags=["健康检查"])
api_router.include_router(user_router, prefix="/api/users", tags=["用户管理"])
