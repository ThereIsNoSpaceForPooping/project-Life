# -*- coding: utf-8 -*-
"""
Sanic Demo - API 路由定义
"""

from app.api.routes.user import bp as user_bp
from app.api.routes.health import bp as health_bp

__all__ = ["user_bp", "health_bp"]
