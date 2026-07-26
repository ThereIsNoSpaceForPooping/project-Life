# -*- coding: utf-8 -*-
"""
Flask Demo - 用户管理路由
"""

from flask import Blueprint, request, jsonify
from pydantic import ValidationError

from app.schemas.user import UserCreate, UserUpdate
from app.services.user_service import UserService

user_bp = Blueprint("users", __name__, url_prefix="/api/users")


@user_bp.route("/", methods=["GET"])
def get_users():
    """获取用户列表 - 支持分页"""
    # 从查询参数获取分页信息
    skip = request.args.get("skip", 0, type=int)
    limit = request.args.get("limit", 10, type=int)
    
    # 参数验证
    if skip < 0:
        skip = 0
    if limit < 1 or limit > 100:
        limit = 10
    
    users = UserService.get_all(skip=skip, limit=limit)
    return jsonify([u.to_dict() for u in users])


@user_bp.route("/<int:user_id>", methods=["GET"])
def get_user(user_id: int):
    """根据 ID 获取用户"""
    user = UserService.get_by_id(user_id)
    if not user:
        return jsonify({"error": f"用户 {user_id} 不存在"}), 404
    return jsonify(user.to_dict())


@user_bp.route("/", methods=["POST"])
def create_user():
    """创建新用户"""
    # 获取请求数据
    data = request.get_json()
    if not data:
        return jsonify({"error": "请求体不能为空"}), 400
    
    # 数据验证
    try:
        user_data = UserCreate(**data)
    except ValidationError as e:
        return jsonify({"error": f"数据验证失败: {str(e)}"}), 400
    
    user = UserService.create(user_data)
    return jsonify(user.to_dict()), 201


@user_bp.route("/<int:user_id>", methods=["PUT"])
def update_user(user_id: int):
    """更新用户信息"""
    # 获取请求数据
    data = request.get_json()
    if not data:
        return jsonify({"error": "请求体不能为空"}), 400
    
    # 数据验证
    try:
        user_data = UserUpdate(**data)
    except ValidationError as e:
        return jsonify({"error": f"数据验证失败: {str(e)}"}), 400
    
    user = UserService.update(user_id, user_data)
    if not user:
        return jsonify({"error": f"用户 {user_id} 不存在"}), 404
    return jsonify(user.to_dict())


@user_bp.route("/<int:user_id>", methods=["DELETE"])
def delete_user(user_id: int):
    """删除用户"""
    success = UserService.delete(user_id)
    if not success:
        return jsonify({"error": f"用户 {user_id} 不存在"}), 404
    return jsonify({"message": f"用户 {user_id} 已删除"})
