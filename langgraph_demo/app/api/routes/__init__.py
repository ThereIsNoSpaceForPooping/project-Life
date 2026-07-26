# -*- coding: utf-8 -*-
"""
API 路由模块
"""

from app.api.routes.health import health_router
from app.api.routes.chat import chat_router

__all__ = ["health_router", "chat_router"]
