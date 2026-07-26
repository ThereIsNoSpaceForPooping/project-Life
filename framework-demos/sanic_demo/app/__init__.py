# -*- coding: utf-8 -*-
"""
Sanic Demo - 应用工厂模块
"""

from sanic import Sanic

from app.core.config import settings
from app.api import register_routes


def create_app() -> Sanic:
    """
    应用工厂函数
    
    Returns:
        Sanic: 配置完成的 Sanic 应用实例
    """
    # 创建 Sanic 应用
    application = Sanic(settings.APP_NAME)
    
    # 注册路由
    register_routes(application)
    
    # 注册中间件
    register_middlewares(application)
    
    return application


def register_middlewares(app: Sanic):
    """注册中间件"""
    
    @app.middleware("request")
    async def log_request(request):
        """请求日志中间件"""
        print(f"[{request.method}] {request.path}")
    
    @app.middleware("response")
    async def add_header(request, response):
        """添加自定义响应头"""
        response.headers["X-Framework"] = "Sanic"
