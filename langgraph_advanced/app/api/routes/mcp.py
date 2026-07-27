# -*- coding: utf-8 -*-
"""
MCP 路由

提供 MCP（Model Context Protocol）功能的 API 接口：
- 列出可用工具
- 调用 MCP 工具
- 管理 MCP Server
"""

from fastapi import APIRouter, HTTPException

from app.agent.mcp import mcp_tool_registry, create_default_mcp_server
from app.schemas.chat import MCPToolCallRequest, MCPToolCallResponse
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()

# 创建默认 MCP Server
mcp_server = create_default_mcp_server()


@router.get("/mcp/tools")
async def list_mcp_tools():
    """
    列出所有 MCP 工具
    
    Returns:
        dict: 工具列表
    """
    try:
        tools = mcp_tool_registry.get_all_tools()
        
        return {
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                    "required": tool.required
                }
                for tool in tools
            ]
        }
    
    except Exception as e:
        logger.error(f"列出 MCP 工具失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mcp/call", response_model=MCPToolCallResponse)
async def call_mcp_tool(request: MCPToolCallRequest):
    """
    调用 MCP 工具
    
    Args:
        request: 工具调用请求（包含 tool_name 和 arguments）
    
    Returns:
        MCPToolCallResponse: 工具执行结果
    """
    try:
        logger.info(f"调用 MCP 工具: {request.tool_name}")
        
        # 获取工具处理器
        handler = mcp_server._tool_handlers.get(request.tool_name)
        if not handler:
            raise HTTPException(
                status_code=404,
                detail=f"工具 '{request.tool_name}' 不存在"
            )
        
        # 执行工具
        result = await handler(**request.arguments)
        
        return MCPToolCallResponse(
            result=str(result),
            is_error=False
        )
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"MCP 工具调用失败: {e}")
        return MCPToolCallResponse(
            result=str(e),
            is_error=True
        )


@router.get("/mcp/server/info")
async def get_mcp_server_info():
    """
    获取 MCP Server 信息
    
    Returns:
        dict: Server 信息
    """
    try:
        return {
            "name": mcp_server.name,
            "version": mcp_server.version,
            "tool_count": len(mcp_server._tool_handlers),
            "tools": list(mcp_server._tool_handlers.keys())
        }
    
    except Exception as e:
        logger.error(f"获取 Server 信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
