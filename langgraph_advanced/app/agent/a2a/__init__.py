# -*- coding: utf-8 -*-
"""
A2A 模块（Google A2A 协议 v0.2 客户端）

A2A（Agent-to-Agent）是 Google 推出的开放协议，
用于标准化 AI Agent 之间的通信和协作。

本模块仅包含客户端（Server 已独立部署在 a2a_server/）。

架构：
    ┌──────────┐   A2A (JSON-RPC 2.0)    ┌──────────┐
    │  Agent   │ ◀──────────────────────▶│ A2A Srv  │
    │ (本项目) │   Streamable HTTP / SSE  │(独立)    │
    └──────────┘                          └──────────┘

文件：
    client.py        真实 A2A 客户端（httpx + JSON-RPC 2.0 + SSE）
    tools_loader.py  将 A2A Agent 包装为 LangChain StructuredTool
"""

from app.agent.a2a.client import A2AClient, A2AError
from app.agent.a2a.tools_loader import (
    A2AToolsLoader,
    A2A_TOOL_PREFIX,
    is_a2a_tool,
    a2a_original_name,
    load_a2a_tools,
    close_a2a_tools,
    a2a_loader,
)

__all__ = [
    "A2AClient",
    "A2AError",
    "A2AToolsLoader",
    "A2A_TOOL_PREFIX",
    "is_a2a_tool",
    "a2a_original_name",
    "load_a2a_tools",
    "close_a2a_tools",
    "a2a_loader",
]
