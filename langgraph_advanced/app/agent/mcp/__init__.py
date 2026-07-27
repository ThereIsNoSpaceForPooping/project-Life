# -*- coding: utf-8 -*-
"""
MCP 模块初始化

MCP（Model Context Protocol）是 Anthropic 推出的开放协议，
用于标准化 AI 模型与外部工具/数据源的通信。

本模块包含：
- transport.py: 传输层实现（stdio / SSE / HTTP）
- tools.py: MCP 工具定义
- server.py: MCP Server 实现
- client.py: MCP Client 实现

架构图：
    ┌─────────────────────────────────────────────────────────────┐
    │                        MCP 架构                              │
    ├─────────────────────────────────────────────────────────────┤
    │                                                              │
    │   ┌──────────┐         ┌──────────┐         ┌──────────┐   │
    │   │   Agent  │ ──────▶ │  Client  │ ──────▶ │  Server  │   │
    │   │  (LLM)   │         │ (MCP)    │         │ (MCP)    │   │
    │   └──────────┘         └──────────┘         └──────────┘   │
    │        │                   │                    │           │
    │        │              ┌────┴────┐          ┌────┴────┐      │
    │        │              │Transport│          │  Tools  │      │
    │        │              │(stdio/  │          │(文件/DB/ │      │
    │        │              │ SSE/HTTP)          │  API)    │      │
    │        │              └─────────┘          └─────────┘      │
    │        │                                                     │
    │   ┌────┴────┐                                                │
    │   │  Tools  │                                                │
    │   │(LangChain)                                              │
    │   └─────────┘                                                │
    │                                                              │
    └─────────────────────────────────────────────────────────────┘

使用示例：
    # 1. 创建 MCP Server
    server = create_default_mcp_server()
    
    # 2. 创建 MCP Client 并连接
    client = MCPClient()
    await client.connect("http", base_url="http://localhost:8080")
    
    # 3. 获取工具列表
    tools = await client.list_tools()
    
    # 4. 调用工具
    result = await client.call_tool("read_file", {"path": "/tmp/test.txt"})
    
    # 5. 转换为 LangChain 工具
    wrapper = MCPToolWrapper(client)
    langchain_tools = await wrapper.get_langchain_tools()
"""

from app.agent.mcp.transport import (
    BaseTransport,
    StdioTransport,
    SSETransport,
    HTTPTransport,
    create_transport,
)

from app.agent.mcp.tools import (
    MCPToolDefinition,
    MCPToolRegistry,
    mcp_tool_registry,
    FILESYSTEM_TOOLS,
    DATABASE_TOOLS,
    COMPUTATION_TOOLS,
    API_TOOLS,
)

from app.agent.mcp.server import (
    MCPServer,
    create_default_mcp_server,
)

from app.agent.mcp.client import (
    MCPClient,
    MCPToolWrapper,
    create_mcp_client,
)

__all__ = [
    # Transport
    "BaseTransport",
    "StdioTransport",
    "SSETransport",
    "HTTPTransport",
    "create_transport",
    
    # Tools
    "MCPToolDefinition",
    "MCPToolRegistry",
    "mcp_tool_registry",
    "FILESYSTEM_TOOLS",
    "DATABASE_TOOLS",
    "COMPUTATION_TOOLS",
    "API_TOOLS",
    
    # Server
    "MCPServer",
    "create_default_mcp_server",
    
    # Client
    "MCPClient",
    "MCPToolWrapper",
    "create_mcp_client",
]
