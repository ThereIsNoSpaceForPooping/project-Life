# -*- coding: utf-8 -*-
"""
Sanic Demo - API 路由模块
"""

from sanic import Sanic

from app.api.routes.user import bp as user_bp
from app.api.routes.health import bp as health_bp
from app.api.routes.stream import bp as stream_bp


def register_routes(app: Sanic):
    """注册所有路由"""
    app.blueprint(health_bp)
    app.blueprint(user_bp)
    app.blueprint(stream_bp)
