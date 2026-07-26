# -*- coding: utf-8 -*-
"""
Flask Demo - 应用工厂模块
"""

from flask import Flask

from app.core.config import settings
from app.api import register_blueprints


def create_app() -> Flask:
    """
    应用工厂函数
    
    Returns:
        Flask: 配置完成的 Flask 应用实例
    """
    # 创建 Flask 应用
    application = Flask(__name__)
    
    # 加载配置
    application.config.from_object(settings)
    
    # 注册蓝图
    register_blueprints(application)
    
    # 注册中间件
    register_middlewares(application)
    
    return application


def register_middlewares(app: Flask):
    """注册中间件"""
    
    @app.before_request
    def log_request():
        """请求日志中间件"""
        from flask import request
        print(f"[{request.method}] {request.path}")
    
    @app.after_request
    def add_header(response):
        """添加自定义响应头"""
        response.headers["X-Framework"] = "Flask"
        return response
