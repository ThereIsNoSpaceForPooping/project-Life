# -*- coding: utf-8 -*-
"""
A2A Server 配置
"""

import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class Config:
    """A2A Server 配置类"""
    
    # 服务器配置
    HOST: str = os.getenv("A2A_SERVER_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("A2A_SERVER_PORT", "8002"))
    
    # LLM 配置
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "minimax")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "MiniMax-M2.7-highspeed")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.minimax.chat/v1")
