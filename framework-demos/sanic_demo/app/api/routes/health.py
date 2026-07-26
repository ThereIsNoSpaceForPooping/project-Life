# -*- coding: utf-8 -*-
"""
Sanic Demo - 健康检查路由
"""

from sanic import Blueprint
from sanic.response import json

bp = Blueprint("health", url_prefix="")


@bp.get("/")
async def root(request):
    """根路径 - 服务信息"""
    return json({
        "framework": "Sanic",
        "version": "1.0.0",
        "status": "running",
        "port": 8002
    })


@bp.get("/health")
async def health_check(request):
    """健康检查接口"""
    return json({"status": "healthy"})
