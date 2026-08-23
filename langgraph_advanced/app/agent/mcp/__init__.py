# -*- coding: utf-8 -*-
"""
MCP 模块（基于 Anthropic 官方 SDK）

MCP（Model Context Protocol）是 Anthropic 推出的开放协议，
用于标准化 AI 模型与外部工具/数据源的通信。

本模块仅包含客户端（Server 已独立部署在 mcp_server/）。

架构：
    ┌──────────┐    MCP (JSON-RPC 2.0)    ┌──────────┐
    │  Agent   │ ◀──────────────────────▶ │ MCP Srv  │
    │ (本项目) │   Streamable HTTP / stdio│ (独立)   │
    └──────────┘                          └──────────┘

文件：
    client.py      真实 MCP 客户端（基于官方 mcp SDK）
    tools_loader.py 将 MCP 工具包装为 LangChain StructuredTool
"""

from app.agent.mcp.client import MCPClient
from app.agent.mcp.tools_loader import (
    MCPToolsLoader,
    MCP_TOOL_PREFIX,
    is_mcp_tool,
    mcp_original_name,
    load_mcp_tools,
    close_mcp_tools,
    mcp_loader,
)

__all__ = [
    "MCPClient",
    "MCPToolsLoader",
    "MCP_TOOL_PREFIX",
    "is_mcp_tool",
    "mcp_original_name",
    "load_mcp_tools",
    "close_mcp_tools",
    "mcp_loader",
]
