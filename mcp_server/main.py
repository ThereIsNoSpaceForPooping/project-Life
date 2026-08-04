# -*- coding: utf-8 -*-
"""
MCP Server - 主入口

提供 MCP 协议的 HTTP 服务端。

v2 功能：
    - 写死响应模式（FAKE_MODE）：用于开发/测试阶段，避免依赖真实文件系统/数据库
    - 生产环境可通过 FAKE_MODE=False 切换回真实工具执行
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
# v2 写死响应模式配置
# ============================================================

# FAKE_MODE 开关：
# - True（默认）：工具调用直接返回写死数据，适用于开发/测试/演示
# - False：执行真实工具逻辑，适用于生产环境
# 
# 使用场景：
# 1. 开发阶段：前端/后端联调时，无需部署真实数据库/文件系统
# 2. 演示阶段：保证工具调用链路完整，展示效果稳定
# 3. 单元测试：避免测试用例依赖外部环境
FAKE_MODE: bool = True

# 写死响应映射表：工具名 → 固定返回值
# 
# 设计原则：
# - 返回值结构与真实工具输出一致（JSON 可序列化）
# - 包含足够的信息量，便于 Agent 组织回答
# - 明确标注"写死数据"，避免用户误以为来自真实数据源
FAKE_RESPONSES: dict[str, dict] = {
    # ========== 文件操作工具 ==========
    "file_read": {
        "content": "【MCP 写死数据】这是 README.md 的内容\n\n# Project Life\n\n这是一个 LangGraph 高级功能演示项目。\n\n## 特性\n- 子图编排\n- 人机协作\n- Map-Reduce 并行\n- MCP 工具集成\n- A2A Agent 协作\n\n## 快速开始\n```bash\npython main.py\n```\n\n（注：此为写死测试数据，非真实文件内容）"
    },
    "file_write": {
        "status": "ok",
        "message": "文件写入成功（写死模式）",
        "path": "output.md",
        "bytes_written": 1024
    },
    "file_list": {
        "files": [
            "README.md",
            "docs/",
            "src/",
            "tests/",
            ".gitignore",
            "requirements.txt"
        ],
        "count": 6
    },
    "file_delete": {
        "status": "ok",
        "message": "文件删除成功（写死模式）",
        "path": "temp.txt"
    },
    
    # ========== 数据库操作工具 ==========
    "db_query": {
        "rows": [
            {"id": 1, "name": "张三", "age": 28, "email": "zhangsan@example.com"},
            {"id": 2, "name": "李四", "age": 32, "email": "lisi@example.com"},
            {"id": 3, "name": "王五", "age": 25, "email": "wangwu@example.com"}
        ],
        "total": 3,
        "columns": ["id", "name", "age", "email"]
    },
    "db_execute": {
        "affected_rows": 1,
        "status": "ok",
        "message": "SQL 执行成功（写死模式）"
    },
    "db_tables": {
        "tables": ["users", "orders", "products", "categories"],
        "count": 4
    },
    "db_schema": {
        "table": "users",
        "columns": [
            {"name": "id", "type": "INT", "nullable": False, "primary_key": True},
            {"name": "name", "type": "VARCHAR(255)", "nullable": False, "primary_key": False},
            {"name": "email", "type": "VARCHAR(255)", "nullable": True, "primary_key": False},
            {"name": "created_at", "type": "TIMESTAMP", "nullable": False, "primary_key": False}
        ]
    },
    
    # ========== HTTP 请求工具 ==========
    "http_request": {
        "status_code": 200,
        "headers": {"Content-Type": "application/json"},
        "body": '{"message": "OK（写死模式）", "timestamp": "2026-08-05T00:00:00Z"}'
    },
    "http_get": {
        "status_code": 200,
        "headers": {"Content-Type": "text/plain"},
        "body": "GET request successful（写死模式）"
    },
    "http_post": {
        "status_code": 201,
        "headers": {"Content-Type": "application/json"},
        "body": '{"id": 101, "created": true, "message": "POST request successful（写死模式）"}'
    },
    
    # ========== 代码执行工具 ==========
    "code_execute": {
        "output": "Hello, World!\n【写死模式】代码执行完成\n",
        "exit_code": 0,
        "execution_time_ms": 15
    },
    "code_evaluate": {
        "result": 42,
        "error": None,
        "type": "integer"
    }
}


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
    
    v2 变更：
        - 支持写死响应模式（FAKE_MODE=True 时直接返回固定数据）
        - 写死模式适用于开发/测试/演示，避免依赖真实环境
    """
    # 检查工具是否存在
    tool = tool_registry.get_tool(request.tool_name)
    if not tool:
        raise HTTPException(
            status_code=404,
            detail=f"工具不存在: {request.tool_name}"
        )
    
    # ============================================================
    # v2: 写死响应模式分支
    # ============================================================
    # 如果 FAKE_MODE 开启，直接从 FAKE_RESPONSES 获取写死数据
    # 这样 Agent 调用工具时能拿到完整数据，链路不会中断
    if FAKE_MODE:
        # 尝试从写死映射表获取固定响应
        if request.tool_name in FAKE_RESPONSES:
            result = FAKE_RESPONSES[request.tool_name]
            print(f"[FAKE_MODE] 工具 {request.tool_name} 返回写死数据")
        else:
            # 如果映射表中没有，返回通用默认值
            result = {
                "status": "ok",
                "message": f"工具 {request.tool_name} 调用成功（写死模式 - 默认响应）",
                "echo_args": request.arguments
            }
            print(f"[FAKE_MODE] 工具 {request.tool_name} 未在映射表中，返回默认数据")
        
        return ToolCallResponse(result=result, is_error=False)
    
    # ============================================================
    # 真实执行模式（FAKE_MODE=False）
    # ============================================================
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
