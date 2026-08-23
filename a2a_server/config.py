# -*- coding: utf-8 -*-
"""
A2A Server 配置
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv(Path(__file__).resolve().parent / ".env")


class Config:
    """A2A Server 配置类"""

    # 服务器配置
    HOST: str = os.getenv("A2A_SERVER_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("A2A_SERVER_PORT", "8002"))

    # 任务配置
    MAX_CONCURRENT_TASKS: int = int(os.getenv("MAX_CONCURRENT_TASKS", "16"))
    TASK_TTL_SECONDS: int = int(os.getenv("TASK_TTL_SECONDS", "3600"))  # 1 小时

    # 日志
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
