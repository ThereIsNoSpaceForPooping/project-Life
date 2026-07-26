# -*- coding: utf-8 -*-
"""
Flask Demo - API 路由模块
"""

from flask import Flask

from app.api.routes.user import user_bp
from app.api.routes.health import health_bp


def register_blueprints(app: Flask):
    """注册所有蓝图"""
    app.register_blueprint(health_bp)
    app.register_blueprint(user_bp)
