# -*- coding: utf-8 -*-
"""
FastAPI Demo - 健康检查路由
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def root():
    """根路径 - 服务信息"""
    return {
        "framework": "FastAPI",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs"
    }


@router.get("/health")
async def health_check():
    """健康检查接口"""
    return {"status": "healthy"}
