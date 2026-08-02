# -*- coding: utf-8 -*-
"""
MCP Server 配置
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class Config:
    """MCP Server 配置类"""
    
    # 服务器配置
    HOST: str = os.getenv("MCP_SERVER_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("MCP_SERVER_PORT", "8001"))
    
    # 文件操作配置
    FILE_ROOT_DIR: Path = Path(os.getenv("FILE_ROOT_DIR", "./files"))
    
    # 数据库配置
    DB_PATH: Path = Path(os.getenv("DB_PATH", "./data/mcp.db"))
    
    @classmethod
    def ensure_dirs(cls):
        """确保必要目录存在"""
        cls.FILE_ROOT_DIR.mkdir(parents=True, exist_ok=True)
        cls.DB_PATH.parent.mkdir(parents=True, exist_ok=True)


# 初始化目录
Config.ensure_dirs()
