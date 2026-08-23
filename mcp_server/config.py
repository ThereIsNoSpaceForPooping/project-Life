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

    # 服务器配置（注意：HOST/PORT 也可由 main.py 通过 FastMCP 实例设置）
    HOST: str = os.getenv("MCP_SERVER_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("MCP_SERVER_PORT", "8001"))

    # 文件操作配置：所有文件操作限制在此目录下（防路径穿越）
    FILE_ROOT_DIR: Path = Path(os.getenv("FILE_ROOT_DIR", "./files")).resolve()

    # 数据库配置：SQLite 文件路径
    DB_PATH: Path = Path(os.getenv("DB_PATH", "./data/mcp.db")).resolve()

    # 日志级别
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

    @classmethod
    def ensure_dirs(cls) -> None:
        """确保必要目录存在"""
        cls.FILE_ROOT_DIR.mkdir(parents=True, exist_ok=True)
        cls.DB_PATH.parent.mkdir(parents=True, exist_ok=True)


# 初始化目录
Config.ensure_dirs()
