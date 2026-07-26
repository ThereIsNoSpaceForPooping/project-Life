# -*- coding: utf-8 -*-
"""
LangGraph Agent Demo - 应用工厂模块
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging
from app.api.routes import health_router, chat_router


def create_app() -> FastAPI:
    """
    应用工厂函数

    Returns:
        FastAPI: 配置完成的 FastAPI 应用实例
    """
    # 初始化日志
    setup_logging()

    # 创建 FastAPI 应用
    application = FastAPI(
        title=settings.APP_NAME,
        description="LangGraph 智能体企业级 Demo",
        version=settings.APP_VERSION,
        docs_url="/docs",
        redoc_url="/redoc"
    )

    # 配置 CORS
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    application.include_router(health_router, tags=["健康检查"])
    application.include_router(chat_router, prefix="/api", tags=["智能体对话"])

    return application
