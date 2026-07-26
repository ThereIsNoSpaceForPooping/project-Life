# -*- coding: utf-8 -*-
"""
FastAPI Demo - API 路由定义
"""

from app.api.routes.user import router as user_router
from app.api.routes.health import router as health_router

__all__ = ["user_router", "health_router"]
