# -*- coding: utf-8 -*-
"""
FastAPI Demo - 用户数据模型
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    """用户基础模型"""
    name: str = Field(..., min_length=1, max_length=50, description="用户名称")
    email: str = Field(..., description="邮箱地址")
    age: Optional[int] = Field(None, ge=0, le=150, description="年龄")


class UserCreate(UserBase):
    """用户创建请求模型"""
    pass


class UserUpdate(BaseModel):
    """用户更新请求模型"""
    name: Optional[str] = Field(None, min_length=1, max_length=50, description="用户名称")
    email: Optional[str] = Field(None, description="邮箱地址")
    age: Optional[int] = Field(None, ge=0, le=150, description="年龄")


class UserResponse(UserBase):
    """用户响应模型"""
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True
