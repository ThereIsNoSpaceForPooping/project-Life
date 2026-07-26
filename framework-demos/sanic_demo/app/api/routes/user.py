# -*- coding: utf-8 -*-
"""
Sanic Demo - 用户管理路由
"""

from sanic import Blueprint
from sanic.response import json
from sanic.exceptions import NotFound
from pydantic import ValidationError

from app.schemas.user import UserCreate, UserUpdate
from app.services.user_service import UserService

bp = Blueprint("users", url_prefix="/api/users")


@bp.get("/")
async def get_users(request):
    """获取用户列表 - 支持分页"""
    # 从查询参数获取分页信息
    skip = int(request.args.get("skip", 0))
    limit = int(request.args.get("limit", 10))
    
    # 参数验证
    if skip < 0:
        skip = 0
    if limit < 1 or limit > 100:
        limit = 10
    
    users = UserService.get_all(skip=skip, limit=limit)
    return json([u.to_dict() for u in users])


@bp.get("/<user_id:int>")
async def get_user(request, user_id: int):
    """根据 ID 获取用户"""
    user = UserService.get_by_id(user_id)
    if not user:
        raise NotFound(f"用户 {user_id} 不存在")
    return json(user.to_dict())


@bp.post("/")
async def create_user(request):
    """创建新用户"""
    # 解析请求体
    try:
        user_data = UserCreate(**request.json)
    except ValidationError as e:
        return json({"error": f"数据验证失败: {str(e)}"}, status=400)
    
    user = UserService.create(user_data)
    return json(user.to_dict(), status=201)


@bp.put("/<user_id:int>")
async def update_user(request, user_id: int):
    """更新用户信息"""
    # 解析请求体
    try:
        user_data = UserUpdate(**request.json)
    except ValidationError as e:
        return json({"error": f"数据验证失败: {str(e)}"}, status=400)
    
    user = UserService.update(user_id, user_data)
    if not user:
        raise NotFound(f"用户 {user_id} 不存在")
    return json(user.to_dict())


@bp.delete("/<user_id:int>")
async def delete_user(request, user_id: int):
    """删除用户"""
    success = UserService.delete(user_id)
    if not success:
        raise NotFound(f"用户 {user_id} 不存在")
    return json({"message": f"用户 {user_id} 已删除"})
