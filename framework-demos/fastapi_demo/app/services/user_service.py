# -*- coding: utf-8 -*-
"""
FastAPI Demo - 用户业务逻辑
"""

from typing import List, Optional
from datetime import datetime

from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


class UserService:
    """用户服务类 - 处理用户相关业务逻辑"""
    
    # 模拟数据库（内存存储）
    _db: List[User] = []
    _next_id: int = 1
    
    @classmethod
    def get_all(cls, skip: int = 0, limit: int = 10) -> List[User]:
        """
        获取所有用户（分页）
        
        Args:
            skip: 跳过条数
            limit: 每页条数
            
        Returns:
            List[User]: 用户列表
        """
        return cls._db[skip:skip + limit]
    
    @classmethod
    def get_by_id(cls, user_id: int) -> Optional[User]:
        """
        根据 ID 获取用户
        
        Args:
            user_id: 用户 ID
            
        Returns:
            Optional[User]: 用户对象，不存在返回 None
        """
        for user in cls._db:
            if user.id == user_id:
                return user
        return None
    
    @classmethod
    def create(cls, user_data: UserCreate) -> User:
        """
        创建用户
        
        Args:
            user_data: 用户创建数据
            
        Returns:
            User: 创建的用户对象
        """
        new_user = User(
            id=cls._next_id,
            name=user_data.name,
            email=user_data.email,
            age=user_data.age,
            created_at=datetime.now()
        )
        cls._db.append(new_user)
        cls._next_id += 1
        return new_user
    
    @classmethod
    def update(cls, user_id: int, user_data: UserUpdate) -> Optional[User]:
        """
        更新用户
        
        Args:
            user_id: 用户 ID
            user_data: 更新数据
            
        Returns:
            Optional[User]: 更新后的用户，不存在返回 None
        """
        user = cls.get_by_id(user_id)
        if not user:
            return None
        
        # 更新字段
        if user_data.name is not None:
            user.name = user_data.name
        if user_data.email is not None:
            user.email = user_data.email
        if user_data.age is not None:
            user.age = user_data.age
        
        return user
    
    @classmethod
    def delete(cls, user_id: int) -> bool:
        """
        删除用户
        
        Args:
            user_id: 用户 ID
            
        Returns:
            bool: 是否删除成功
        """
        for i, user in enumerate(cls._db):
            if user.id == user_id:
                cls._db.pop(i)
                return True
        return False
