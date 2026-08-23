# -*- coding: utf-8 -*-
"""
MCP 真实客户端（基于 Anthropic 官方 SDK）

使用 mcp.client 提供的 ClientSession，通过 Streamable HTTP
或 stdio 连接到外部 MCP Server。

使用官方 SDK 意味着：
    - 自动处理 JSON-RPC 2.0 协议
    - 自动处理 initialize / tools/list / tools/call 流程
    - 自动维护会话状态

典型用法：
    from app.agent.mcp.client import MCPClient

    client = MCPClient("http://localhost:8001/mcp")
    await client.connect()
    tools = await client.list_tools()
    result = await client.call_tool("file_read", {"path": "test.txt"})
    await client.close()
"""

import asyncio
import logging
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional

# 官方 MCP Python SDK
try:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client
    from mcp.client.stdio import stdio_client, StdioServerParameters
    from mcp.types import Tool as MCPSchema
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "缺少 mcp SDK，请执行: pip install mcp[cli]"
    ) from exc

from app.core.logging import get_logger

logger: logging.Logger = get_logger(__name__)


class MCPClient:
    """
    MCP 真实客户端

    基于 Anthropic 官方 Python SDK 实现。
    支持：
        - Streamable HTTP 传输（推荐用于远程 Server）
        - stdio 传输（推荐用于本地进程）
    """

    def __init__(
        self,
        url: Optional[str] = None,
        command: Optional[str] = None,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        初始化客户端（二选一）

        Args:
            url: Streamable HTTP 端点（如 "http://localhost:8001/mcp"）
            command: stdio 模式的命令（如 "python"）
            args: stdio 模式的参数列表
            env: stdio 模式的环境变量
        """
        self.url: Optional[str] = url
        self.command: Optional[str] = command
        self.args: List[str] = args or []
        self.env: Optional[Dict[str, str]] = env

        self._exit_stack: AsyncExitStack = AsyncExitStack()
        self._session: Optional[ClientSession] = None
        self._connected: bool = False

    async def connect(self) -> None:
        """
        建立连接并完成 MCP 协议初始化握手

        MCP 协议要求客户端在发送任何业务请求前先完成 initialize 流程。
        官方 ClientSession 会在 __aenter__ 阶段自动完成。
        """
        if self._connected:
            return

        try:
            if self.url:
                # Streamable HTTP 传输
                read_stream, write_stream, _ = (
                    await self._exit_stack.enter_async_context(
                        streamablehttp_client(self.url)
                    )
                )
            elif self.command:
                # stdio 传输
                params: StdioServerParameters = StdioServerParameters(
                    command=self.command,
                    args=self.args,
                    env=self.env,
                )
                read_stream, write_stream = (
                    await self._exit_stack.enter_async_context(
                        stdio_client(params)
                    )
                )
            else:
                raise ValueError("必须指定 url 或 command 之一")

            # 创建 ClientSession
            self._session = await self._exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )

            # 触发 initialize 握手
            init_result = await self._session.initialize()

            logger.info(
                "[MCPClient] 已连接: server='%s', version='%s'",
                init_result.serverInfo.name,
                init_result.protocolVersion,
            )
            self._connected = True

        except Exception as exc:
            logger.error("[MCPClient] 连接失败: %s", exc)
            await self._exit_stack.aclose()
            self._exit_stack = AsyncExitStack()
            raise

    async def list_tools(self) -> List[Dict[str, Any]]:
        """
        获取 MCP Server 提供的所有工具

        返回每个工具的：
            - name        工具名
            - description 描述
            - inputSchema 参数 JSON Schema
            - annotations 工具标注（readOnly / destructive 等）
        """
        if not self._connected or not self._session:
            raise RuntimeError("Client 未连接，请先调用 await client.connect()")

        response = await self._session.list_tools()
        tools: List[Dict[str, Any]] = []
        for tool in response.tools:
            tools.append(
                {
                    "name": tool.name,
                    "description": tool.description or "",
                    "inputSchema": tool.inputSchema,
                    "annotations": tool.annotations.model_dump()
                    if tool.annotations
                    else {},
                }
            )
        logger.info("[MCPClient] 工具列表: %d 个", len(tools))
        return tools

    async def call_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        调用 MCP 工具

        Args:
            name: 工具名称
            arguments: 工具参数

        Returns:
            {
                "content": [
                    {"type": "text", "text": "..."},
                    ...
                ],
                "isError": False/True
            }
        """
        if not self._connected or not self._session:
            raise RuntimeError("Client 未连接，请先调用 await client.connect()")

        logger.info(
            "[MCPClient] 调用工具: %s, 参数: %s",
            name, list(arguments.keys()),
        )

        result = await self._session.call_tool(name, arguments)

        # 解析 content
        content: List[Dict[str, Any]] = []
        for item in result.content:
            if hasattr(item, "text"):
                content.append({"type": "text", "text": item.text})
            elif hasattr(item, "data"):
                content.append({"type": "data", "data": item.data})
            elif hasattr(item, "blob"):
                content.append(
                    {
                        "type": "file",
                        "blob": item.blob,
                        "mimeType": getattr(item, "mimeType", None),
                    }
                )
            else:
                content.append({"type": "unknown", "raw": str(item)})

        return {
            "content": content,
            "isError": getattr(result, "isError", False),
        }

    async def close(self) -> None:
        """关闭连接"""
        if self._connected:
            await self._exit_stack.aclose()
            self._exit_stack = AsyncExitStack()
            self._session = None
            self._connected = False
            logger.info("[MCPClient] 已关闭连接")
