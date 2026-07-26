# -*- coding: utf-8 -*-
"""
FastAPI Demo - 用户数据模型（数据库实体）

注：实际项目中这里会使用 SQLAlchemy 等 ORM 定义数据库表
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class User:
    """用户数据实体"""
    id: int
    name: str
    email: str
    age: Optional[int]
    created_at: datetime
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "age": self.age,
            "created_at": self.created_at.isoformat()
        }
