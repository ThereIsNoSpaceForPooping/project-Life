# -*- coding: utf-8 -*-
"""
工具管理器（共享组件）

统一管理本地工具 + MCP 动态工具 + A2A 动态工具。
所有图通过 tool_manager 获取工具列表。
"""

from typing import Optional

from app.agent.shared.tools import TOOLS as LOCAL_TOOLS
from app.core.logging import get_logger

logger = get_logger(__name__)


class ToolManager:
    """
    工具管理器

    职责：
    1. 管理本地工具（TOOLS）和从 MCP Server 动态加载的工具
    2. 提供统一的 get_all_tools() 接口供 Agent 绑定
    3. 提供 find_tool() 接口供 tool_node 查找工具
    """

    def __init__(self):
        # 本地工具（静态，启动时即固定）
        self._local_tools = list(LOCAL_TOOLS)
        # MCP 动态工具（启动后由 load_mcp_tools() 填充）
        self._mcp_tools: list = []
        # A2A 动态工具（启动后由 load_a2a_tools() 填充）
        self._a2a_tools: list = []
        # 合并后的工具列表（懒加载缓存）
        self._all_tools: Optional[list] = None

    def set_mcp_tools(self, mcp_tools: list) -> None:
        """
        设置 MCP 动态工具列表（由启动流程调用）

        Args:
            mcp_tools: 从 MCP Server 加载的 StructuredTool 列表
        """
        self._mcp_tools = mcp_tools
        self._all_tools = None  # 清除缓存，下次 get_all_tools() 时重建

    def set_a2a_tools(self, a2a_tools: list) -> None:
        """
        设置 A2A 动态工具列表（由启动流程调用）

        Args:
            a2a_tools: 从 A2A Server 加载的 StructuredTool 列表
        """
        self._a2a_tools = a2a_tools
        self._all_tools = None  # 清除缓存，下次 get_all_tools() 时重建

    def get_all_tools(self) -> list:
        """
        获取所有可用工具（本地 + MCP + A2A）

        Returns:
            合并后的工具列表
        """
        if self._all_tools is None:
            self._all_tools = self._local_tools + self._mcp_tools + self._a2a_tools
        return self._all_tools

    def find_tool(self, tool_name: str):
        """
        根据名称查找工具

        Args:
            tool_name: 工具名称

        Returns:
            工具实例，未找到返回 None
        """
        for t in self.get_all_tools():
            if t.name == tool_name:
                return t
        return None


# 全局工具管理器实例
tool_manager = ToolManager()
