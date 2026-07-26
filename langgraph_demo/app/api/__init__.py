# -*- coding: utf-8 -*-
"""
API 模块
"""

from app.api.routes import health_router, chat_router

__all__ = ["health_router", "chat_router"]
