# -*- coding: utf-8 -*-
"""
MCP Server - 工具模块

通过 register_*_tools(mcp) 函数将各领域工具注册到 FastMCP 实例。
所有工具遵循 MCP 规范 2025-03-26，使用 @mcp.tool() 装饰器声明。
"""

from tools.file_tools import register_file_tools
from tools.db_tools import register_db_tools
from tools.http_tools import register_http_tools
from tools.code_tools import register_code_tools

__all__ = [
    "register_file_tools",
    "register_db_tools",
    "register_http_tools",
    "register_code_tools",
]
