# -*- coding: utf-8 -*-
"""
应用模块初始化

创建 FastAPI 应用实例并配置中间件。
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.core.config import settings
from app.core.logging import setup_logging

# 配置日志
setup_logging()

# 创建 FastAPI 应用
app = FastAPI(
    title=settings.APP_NAME,
    description="LangGraph 高级功能演示 - 包含子图、人机协作、并行执行、Map-Reduce、动态工具、时间旅行、MCP、A2A",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(api_router)

__all__ = ["app"]
