# -*- coding: utf-8 -*-
"""
FastAPI Demo - 用户管理路由
"""

from typing import List
from fastapi import APIRouter, HTTPException, Query

from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.services.user_service import UserService

router = APIRouter()


@router.get("/", response_model=List[UserResponse])
async def get_users(
    skip: int = Query(0, ge=0, description="跳过条数"),
    limit: int = Query(10, ge=1, le=100, description="每页条数")
):
    """获取用户列表 - 支持分页"""
    users = UserService.get_all(skip=skip, limit=limit)
    return users


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int):
    """根据 ID 获取用户"""
    user = UserService.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"用户 {user_id} 不存在")
    return user


@router.post("/", response_model=UserResponse, status_code=201)
async def create_user(user_data: UserCreate):
    """创建新用户"""
    user = UserService.create(user_data)
    return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(user_id: int, user_data: UserUpdate):
    """更新用户信息"""
    user = UserService.update(user_id, user_data)
    if not user:
        raise HTTPException(status_code=404, detail=f"用户 {user_id} 不存在")
    return user


@router.delete("/{user_id}")
async def delete_user(user_id: int):
    """删除用户"""
    success = UserService.delete(user_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"用户 {user_id} 不存在")
    return {"message": f"用户 {user_id} 已删除"}
