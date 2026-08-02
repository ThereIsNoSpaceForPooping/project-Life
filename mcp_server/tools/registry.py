# -*- coding: utf-8 -*-
"""
MCP Server - 工具注册表

集中管理所有工具。
"""

from tools.file_tools import FILE_TOOLS
from tools.db_tools import DB_TOOLS
from tools.http_tools import HTTP_TOOLS
from tools.code_tools import CODE_TOOLS


class ToolRegistry:
    """工具注册表"""
    
    def __init__(self):
        self._tools = {}
        self._register_all()
    
    def _register_all(self):
        """注册所有工具"""
        all_tools = FILE_TOOLS + DB_TOOLS + HTTP_TOOLS + CODE_TOOLS
        
        for tool in all_tools:
            self._tools[tool["name"]] = tool
    
    def get_tool(self, name: str) -> dict:
        """获取工具"""
        return self._tools.get(name)
    
    def get_all_tools(self) -> list:
        """获取所有工具列表"""
        return [
            {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["parameters"]
            }
            for tool in self._tools.values()
        ]
    
    async def call_tool(self, name: str, arguments: dict) -> dict:
        """
        调用工具
        
        Args:
            name: 工具名称
            arguments: 工具参数
        
        Returns:
            工具执行结果
        """
        tool = self.get_tool(name)
        
        if not tool:
            return {"error": f"工具不存在: {name}"}
        
        handler = tool["handler"]
        
        try:
            return await handler(**arguments)
        except Exception as e:
            return {"error": f"工具执行失败: {str(e)}"}


# 全局工具注册表
tool_registry = ToolRegistry()
