# -*- coding: utf-8 -*-
"""
应用配置模块

从环境变量 / .env 文件加载配置
"""

import os
from typing import List
from pathlib import Path

from dotenv import load_dotenv

# 加载 .env 文件
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)


class Settings:
    """应用配置类"""

    # ---- 应用信息 ----
    APP_NAME: str = os.getenv("APP_NAME", "LangGraph Agent Demo")
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = os.getenv("APP_ENV", "development")

    # ---- 服务配置 ----
    HOST: str = "0.0.0.0"
    PORT: int = 8004

    # ---- 日志配置 ----
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # ---- CORS 配置 ----
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://localhost:5500",
    ]

    # ---- LLM 配置 ----
    MINIMAX_API_KEY: str = os.getenv("MINIMAX_API_KEY", "")
    MINIMAX_BASE_URL: str = os.getenv("MINIMAX_BASE_URL", "https://api.minimax.chat/v1")
    MINIMAX_MODEL: str = "MiniMax-M2.7"

    DASHSCOPE_API_KEY: str = os.getenv("DASHSCOPE_API_KEY", "")
    DASHSCOPE_BASE_URL: str = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    DASHSCOPE_MODEL: str = "qwen-plus"

    # ---- Agent 配置 ----
    DEFAULT_PROVIDER: str = os.getenv("DEFAULT_PROVIDER", "dashscope")  # 默认 LLM 提供商
    MAX_ITERATIONS: int = 10           # Agent 最大思考轮数
    TEMPERATURE: float = 0.7           # 默认温度


# 全局配置实例
settings = Settings()
