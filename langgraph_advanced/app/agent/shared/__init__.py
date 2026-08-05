# -*- coding: utf-8 -*-
"""
共享基础设施模块

统一导出 LLM 工厂、工具管理器、本地工具集、Map-Reduce 工具函数。
所有图（single / master / multi / subagent）共享这些组件。
"""

from app.agent.shared.llm import get_llm
from app.agent.shared.tool_manager import ToolManager, tool_manager
from app.agent.shared.tools import (
    TOOLS,
    get_weather,
    calculate,
    search_knowledge,
    web_search,
    get_current_time,
    TOOL_CATEGORIES,
    get_tools_by_category,
    get_tools_by_names,
)
from app.agent.shared.mapreduce_utils import (
    MAX_CHUNK_CHARS,
    split_text,
    map_summarize_chunk,
)

__all__ = [
    # LLM 工厂
    "get_llm",
    # 工具管理
    "ToolManager",
    "tool_manager",
    # 本地工具
    "TOOLS",
    "get_weather",
    "calculate",
    "search_knowledge",
    "web_search",
    "get_current_time",
    "TOOL_CATEGORIES",
    "get_tools_by_category",
    "get_tools_by_names",
    # Map-Reduce 工具函数
    "MAX_CHUNK_CHARS",
    "split_text",
    "map_summarize_chunk",
]
