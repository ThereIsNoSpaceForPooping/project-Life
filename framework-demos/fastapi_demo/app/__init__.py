# -*- coding: utf-8 -*-
"""
FastAPI Demo - 应用工厂模块
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api import api_router


def create_app() -> FastAPI:
    """
    应用工厂函数
    
    Returns:
        FastAPI: 配置完成的 FastAPI 应用实例
    """
    # 创建 FastAPI 应用
    application = FastAPI(
        title=settings.APP_NAME,
        description=settings.APP_DESCRIPTION,
        version=settings.APP_VERSION,
        docs_url="/docs",
        redoc_url="/redoc"
    )
    
    # 配置 CORS 中间件
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 注册路由
    application.include_router(api_router)
    
    return application
