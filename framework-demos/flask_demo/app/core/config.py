# -*- coding: utf-8 -*-
"""
Flask Demo - 应用配置
"""

from typing import List


class Settings:
    """应用配置类"""
    
    # 应用信息
    APP_NAME: str = "FlaskDemo"
    APP_DESCRIPTION: str = "Flask 企业级分层架构演示"
    APP_VERSION: str = "1.0.0"
    
    # 服务配置
    HOST: str = "0.0.0.0"
    PORT: int = 8003
    
    # Flask 配置
    DEBUG: bool = True
    JSON_AS_ASCII: bool = False  # 支持中文
    
    # CORS 配置
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
    ]
    
    # 分页默认配置
    DEFAULT_PAGE_SIZE: int = 10
    MAX_PAGE_SIZE: int = 100


# 全局配置实例
settings = Settings()
