# -*- coding: utf-8 -*-
"""
健康检查路由
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "service": "LangGraph Advanced Demo",
        "version": "1.0.0"
    }
