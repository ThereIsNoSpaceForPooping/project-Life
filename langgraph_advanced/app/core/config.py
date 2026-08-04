# -*- coding: utf-8 -*-
"""
应用配置
"""

import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# 加载 .env 文件
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)


class Settings(BaseSettings):
    """应用配置"""
    
    # 应用信息
    APP_NAME: str = os.getenv("APP_NAME", "LangGraph Advanced Demo")
    APP_ENV: str = os.getenv("APP_ENV", "development")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # 服务配置
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8005"))
    
    # CORS 配置
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8005",
    ]
    
    # LLM 配置
    MINIMAX_API_KEY: str = os.getenv("MINIMAX_API_KEY", "")
    MINIMAX_BASE_URL: str = os.getenv("MINIMAX_BASE_URL", "https://api.minimax.chat/v1")
    MINIMAX_MODEL: str = "MiniMax-M2.7"
    
    DASHSCOPE_API_KEY: str = os.getenv("DASHSCOPE_API_KEY", "")
    DASHSCOPE_BASE_URL: str = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    DASHSCOPE_MODEL: str = "qwen3.7-plus"
    
    DEFAULT_PROVIDER: str = os.getenv("DEFAULT_PROVIDER", "dashscope")
    TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.7"))
    MAX_ITERATIONS: int = int(os.getenv("MAX_ITERATIONS", "10"))
    
    # 人机协作
    ENABLE_HUMAN_REVIEW: bool = os.getenv("ENABLE_HUMAN_REVIEW", "false").lower() == "true"
    
    # 记忆配置
    MEMORY_BACKEND: str = os.getenv("MEMORY_BACKEND", "memory")
    SQLITE_DB_PATH: str = os.getenv("SQLITE_DB_PATH", "data/memory.db")
    
    # 工具配置
    USE_REAL_API: bool = os.getenv("USE_REAL_API", "true").lower() == "true"
    WEATHER_API_KEY: str = os.getenv("WEATHER_API_KEY", "")
    SEARCH_MAX_RESULTS: int = int(os.getenv("SEARCH_MAX_RESULTS", "5"))
    
    # MCP / A2A 服务地址
    MCP_SERVER_URL: str = os.getenv("MCP_SERVER_URL", "http://localhost:8001")
    A2A_SERVER_URL: str = os.getenv("A2A_SERVER_URL", "http://localhost:8002")
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
