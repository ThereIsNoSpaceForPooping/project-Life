# -*- coding: utf-8 -*-
"""
MCP 路由（代理到独立 mcp_server/）

本路由不再本地实现 MCP Server，而是作为代理转发到
mcp_server/ 进程（8001 端口）。这样保持了架构的清晰：
    langgraph_advanced → MCP Client → 独立 mcp_server

提供接口：
- GET  /mcp/tools      列出可用工具（代理）
- POST /mcp/call       调用工具（代理）
- GET  /mcp/server/info MCP Server 信息
"""

import logging
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException

from app.agent.mcp.tools_loader import mcp_loader
from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.chat import MCPToolCallRequest, MCPToolCallResponse

logger: logging.Logger = get_logger(__name__)

router: APIRouter = APIRouter()


# ============================================================
# 辅助：直接调用独立 mcp_server 的 HTTP 端点
# ============================================================
def _mcp_base_url() -> str:
    """获取独立 mcp_server 的根 URL"""
    return getattr(settings, "MCP_SERVER_URL", "http://localhost:8001").rstrip("/")


@router.get("/mcp/tools")
async def list_mcp_tools() -> Dict[str, Any]:
    """
    列出所有 MCP 工具

    Returns:
        dict: 工具列表
    """
    try:
        # 优先使用本进程内已缓存的 loader
        if mcp_loader and mcp_loader.client and mcp_loader.client._connected:
            tools: List[Dict[str, Any]] = await mcp_loader.client.list_tools()
            return {
                "tools": [
                    {
                        "name": t["name"],
                        "description": t.get("description", ""),
                        "inputSchema": t.get("inputSchema", {}),
                    }
                    for t in tools
                ]
            }

        # 否则通过 HTTP 直接拉取
        async with httpx.AsyncClient(timeout=10.0) as client:
            response: httpx.Response = await client.get(
                f"{_mcp_base_url()}/mcp/tools/list"
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as exc:
        logger.error("调用 mcp_server 失败: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"MCP Server 不可达: {exc}",
        ) from exc
    except Exception as exc:
        logger.error("列出 MCP 工具失败: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/mcp/call", response_model=MCPToolCallResponse)
async def call_mcp_tool(request: MCPToolCallRequest) -> MCPToolCallResponse:
    """
    调用 MCP 工具（代理到独立 mcp_server）

    Args:
        request: 工具调用请求

    Returns:
        工具执行结果
    """
    try:
        logger.info(
            "[routes/mcp] 转发调用: %s, 参数: %s",
            request.tool_name, list(request.arguments.keys()),
        )

        if mcp_loader and mcp_loader.client and mcp_loader.client._connected:
            # 走 SDK ClientSession
            result: Dict[str, Any] = await mcp_loader.client.call_tool(
                request.tool_name, request.arguments
            )
            content_text: str = "\n".join(
                item.get("text", "")
                for item in result.get("content", [])
                if item.get("type") == "text"
            )
            return MCPToolCallResponse(
                result=content_text or str(result),
                is_error=result.get("isError", False),
            )

        # 备选：HTTP POST 到 mcp_server
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{_mcp_base_url()}/mcp/tools/call",
                json={
                    "name": request.tool_name,
                    "arguments": request.arguments,
                },
            )
            response.raise_for_status()
            data: Dict[str, Any] = response.json()
            return MCPToolCallResponse(
                result=str(data.get("result", data)),
                is_error=data.get("isError", False),
            )
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        logger.error("调用 mcp_server 失败: %s", exc)
        raise HTTPException(
            status_code=502, detail=f"MCP Server 不可达: {exc}"
        ) from exc
    except Exception as exc:
        logger.error("MCP 工具调用失败: %s", exc)
        return MCPToolCallResponse(result=str(exc), is_error=True)


@router.get("/mcp/server/info")
async def get_mcp_server_info() -> Dict[str, Any]:
    """
    获取 MCP Server 信息

    Returns:
        dict: Server 信息
    """
    return {
        "name": "project-life-mcp",
        "version": "1.0.0",
        "transport": "streamable-http",
        "url": _mcp_base_url(),
        "loaded_locally": mcp_loader is not None
        and mcp_loader.client is not None
        and mcp_loader.client._connected,
    }
