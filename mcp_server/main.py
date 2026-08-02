# -*- coding: utf-8 -*-
"""
MCP Server - 主入口

提供 MCP 协议的 HTTP 服务端。
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional

from config import Config
from tools.registry import tool_registry

# 创建 FastAPI 应用
app = FastAPI(
    title="MCP Server",
    description="Model Context Protocol Server - 提供工具调用能力",
    version="1.0.0"
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# 请求/响应模型
# ============================================================

class ToolCallRequest(BaseModel):
    """工具调用请求"""
    tool_name: str
    arguments: Dict[str, Any] = {}


class ToolCallResponse(BaseModel):
    """工具调用响应"""
    result: Any
    is_error: bool = False


class ToolInfo(BaseModel):
    """工具信息"""
    name: str
    description: str
    parameters: Dict[str, Any]


# ============================================================
# API 接口
# ============================================================

@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "service": "mcp_server"}


@app.get("/mcp/tools/list", response_model=list[ToolInfo])
async def list_tools():
    """
    列出所有可用工具
    
    Returns:
        工具列表
    """
    return tool_registry.get_all_tools()


@app.post("/mcp/tools/call", response_model=ToolCallResponse)
async def call_tool(request: ToolCallRequest):
    """
    调用指定工具
    
    Args:
        request: 工具调用请求
    
    Returns:
        工具执行结果
    """
    # 检查工具是否存在
    tool = tool_registry.get_tool(request.tool_name)
    if not tool:
        raise HTTPException(
            status_code=404,
            detail=f"工具不存在: {request.tool_name}"
        )
    
    # 调用工具
    result = await tool_registry.call_tool(
        request.tool_name,
        request.arguments
    )
    
    # 检查是否有错误
    is_error = isinstance(result, dict) and "error" in result
    
    return ToolCallResponse(
        result=result,
        is_error=is_error
    )


@app.get("/mcp/tools/{tool_name}", response_model=ToolInfo)
async def get_tool_info(tool_name: str):
    """
    获取工具详情
    
    Args:
        tool_name: 工具名称
    
    Returns:
        工具信息
    """
    tool = tool_registry.get_tool(tool_name)
    
    if not tool:
        raise HTTPException(
            status_code=404,
            detail=f"工具不存在: {tool_name}"
        )
    
    return ToolInfo(
        name=tool["name"],
        description=tool["description"],
        parameters=tool["parameters"]
    )


# ============================================================
# 启动入口
# ============================================================

if __name__ == "__main__":
    import uvicorn
    
    print(f"""
╔═══════════════════════════════════════════════════════════╗
║                    MCP Server                             ║
╠═══════════════════════════════════════════════════════════╣
║  端口: {Config.PORT}                                        ║
║  工具数量: {len(tool_registry.get_all_tools())}                              ║
║                                                           ║
║  可用工具:                                                ║
║  - file_read / file_write / file_list / file_delete       ║
║  - db_query / db_execute / db_tables / db_schema          ║
║  - http_request / http_get / http_post                    ║
║  - code_execute / code_evaluate                           ║
╚═══════════════════════════════════════════════════════════╝
    """)
    
    uvicorn.run(
        app,
        host=Config.HOST,
        port=Config.PORT
    )
