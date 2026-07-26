# -*- coding: utf-8 -*-
"""
Flask Demo - API 路由定义
"""

from app.api.routes.user import user_bp
from app.api.routes.health import health_bp

__all__ = ["user_bp", "health_bp"]
