# -*- coding: utf-8 -*-
"""
Flask Demo - 健康检查路由
"""

from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.route("/")
def root():
    """根路径 - 服务信息"""
    return jsonify({
        "framework": "Flask",
        "version": "1.0.0",
        "status": "running",
        "port": 8003
    })


@health_bp.route("/health")
def health_check():
    """健康检查接口"""
    return jsonify({"status": "healthy"})
