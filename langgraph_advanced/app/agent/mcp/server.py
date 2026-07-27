# -*- coding: utf-8 -*-
"""
MCP Server 实现

MCP Server 是提供工具/资源的服务端。
Agent 通过 MCP Client 连接到 MCP Server，调用工具。

学习要点：
1. MCP Server 暴露工具列表和调用接口
2. 使用 JSON-RPC 2.0 协议通信
3. 支持 stdio / SSE / HTTP 传输方式
4. Server 可以运行在本地或远程

架构图：
    MCP Server
    ├─ tools/list      → 返回可用工具列表
    ├─ tools/call      → 调用指定工具
    ├─ resources/list  → 返回可用资源列表
    └─ resources/read  → 读取指定资源
"""

import json
import asyncio
from typing import Any, Dict, List, Optional

from app.agent.mcp.tools import mcp_tool_registry, MCPToolDefinition
from app.agent.mcp.transport import BaseTransport, StdioTransport, SSETransport
from app.core.logging import get_logger

logger = get_logger(__name__)


# ============================================================
# MCP Server 类
# ============================================================
class MCPServer:
    """
    MCP Server - 提供工具/资源的服务端
    
    职责：
    1. 注册和管理工具
    2. 处理 JSON-RPC 请求
    3. 通过传输层与 Client 通信
    
    使用示例：
        server = MCPServer(name="my-server")
        server.register_tool(my_tool_definition, my_tool_handler)
        await server.start(transport)
    """
    
    def __init__(self, name: str = "mcp-server", version: str = "1.0.0"):
        """
        初始化 MCP Server
        
        Args:
            name: Server 名称
            version: Server 版本
        """
        self.name = name
        self.version = version
        self._tool_handlers: Dict[str, callable] = {}
        self._transport: Optional[BaseTransport] = None
        self._running = False
        
        logger.info(f"MCP Server 初始化: {name} v{version}")
    
    def register_tool(self, tool_def: MCPToolDefinition, handler: callable):
        """
        注册工具及其处理函数
        
        Args:
            tool_def: 工具定义
            handler: 工具处理函数（异步）
        
        使用示例：
            async def read_file_handler(path: str, encoding: str = "utf-8"):
                with open(path, "r", encoding=encoding) as f:
                    return f.read()
            
            server.register_tool(
                MCPToolDefinition(name="read_file", description="读取文件"),
                read_file_handler
            )
        """
        mcp_tool_registry.register(tool_def)
        self._tool_handlers[tool_def.name] = handler
        logger.info(f"注册工具: {tool_def.name}")
    
    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理 JSON-RPC 请求
        
        JSON-RPC 2.0 格式：
        {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "read_file", "arguments": {"path": "/tmp/test.txt"}},
            "id": 1
        }
        
        Args:
            request: JSON-RPC 请求
        
        Returns:
            Dict: JSON-RPC 响应
        """
        method = request.get("method", "")
        params = request.get("params", {})
        request_id = request.get("id")
        
        logger.info(f"处理请求: method={method}, id={request_id}")
        
        try:
            # 路由到对应的处理方法
            if method == "initialize":
                result = self._handle_initialize(params)
            elif method == "tools/list":
                result = self._handle_tools_list(params)
            elif method == "tools/call":
                result = await self._handle_tools_call(params)
            elif method == "resources/list":
                result = self._handle_resources_list(params)
            elif method == "ping":
                result = {}
            else:
                return {
                    "jsonrpc": "2.0",
                    "error": {"code": -32601, "message": f"未知方法: {method}"},
                    "id": request_id,
                }
            
            return {
                "jsonrpc": "2.0",
                "result": result,
                "id": request_id,
            }
        
        except Exception as e:
            logger.error(f"处理请求失败: {e}")
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32000, "message": str(e)},
                "id": request_id,
            }
    
    def _handle_initialize(self, params: Dict) -> Dict:
        """
        处理 initialize 请求
        
        返回 Server 的能力信息。
        """
        return {
            "protocolVersion": "2024-11-05",
            "serverInfo": {
                "name": self.name,
                "version": self.version,
            },
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"listChanged": False},
            },
        }
    
    def _handle_tools_list(self, params: Dict) -> Dict:
        """
        处理 tools/list 请求
        
        返回所有可用工具的定义。
        """
        tools = mcp_tool_registry.get_all_tools()
        return {
            "tools": [
                {
                    "name": t.name,
                    "description": t.description,
                    "inputSchema": t.parameters,
                }
                for t in tools
            ]
        }
    
    async def _handle_tools_call(self, params: Dict) -> Dict:
        """
        处理 tools/call 请求
        
        调用指定的工具并返回结果。
        """
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        
        logger.info(f"调用工具: {tool_name}, 参数: {arguments}")
        
        # 查找工具处理函数
        handler = self._tool_handlers.get(tool_name)
        if not handler:
            return {
                "content": [{"type": "text", "text": f"错误: 未找到工具 '{tool_name}'"}],
                "isError": True,
            }
        
        # 调用工具
        try:
            result = await handler(**arguments)
            return {
                "content": [{"type": "text", "text": str(result)}],
                "isError": False,
            }
        except Exception as e:
            logger.error(f"工具调用失败: {e}")
            return {
                "content": [{"type": "text", "text": f"工具执行失败: {str(e)}"}],
                "isError": True,
            }
    
    def _handle_resources_list(self, params: Dict) -> Dict:
        """处理 resources/list 请求"""
        return {"resources": []}
    
    async def start(self, transport: BaseTransport):
        """
        启动 Server
        
        开始监听并处理请求。
        
        Args:
            transport: 传输层实例
        """
        self._transport = transport
        self._running = True
        logger.info(f"MCP Server 启动: {self.name}")
        
        while self._running:
            try:
                # 接收请求
                request = await transport.receive()
                
                if request is None:
                    # 连接关闭
                    break
                
                # 处理请求
                response = await self.handle_request(request)
                
                # 发送响应
                await transport.send(response)
            
            except Exception as e:
                logger.error(f"Server 循环错误: {e}")
                break
        
        await self.stop()
    
    async def stop(self):
        """停止 Server"""
        self._running = False
        if self._transport:
            await self._transport.close()
        logger.info(f"MCP Server 停止: {self.name}")


# ============================================================
# 内置工具处理函数
# ============================================================
async def read_file_handler(path: str, encoding: str = "utf-8") -> str:
    """读取文件内容"""
    try:
        with open(path, "r", encoding=encoding) as f:
            return f.read()
    except Exception as e:
        return f"读取文件失败: {e}"


async def write_file_handler(path: str, content: str, encoding: str = "utf-8") -> str:
    """写入文件内容"""
    try:
        with open(path, "w", encoding=encoding) as f:
            f.write(content)
        return f"文件写入成功: {path}"
    except Exception as e:
        return f"写入文件失败: {e}"


async def list_directory_handler(path: str = ".") -> str:
    """列出目录内容"""
    import os
    try:
        entries = os.listdir(path)
        return "\n".join(sorted(entries))
    except Exception as e:
        return f"列出目录失败: {e}"


async def math_calculate_handler(expression: str) -> str:
    """数学计算"""
    try:
        allowed_chars = set('0123456789+-*/.() ')
        if not all(c in allowed_chars for c in expression):
            return "错误: 表达式包含非法字符"
        result = eval(expression, {"__builtins__": {}}, {})
        return str(result)
    except Exception as e:
        return f"计算失败: {e}"


# ============================================================
# 创建默认 Server
# ============================================================
def create_default_mcp_server() -> MCPServer:
    """
    创建带有默认工具的 MCP Server
    
    默认包含：
    - 文件系统工具（read_file, write_file, list_directory）
    - 计算工具（math_calculate）
    
    Returns:
        MCPServer: 配置好的 Server 实例
    """
    from app.agent.mcp.tools import FILESYSTEM_TOOLS, COMPUTATION_TOOLS
    
    server = MCPServer(name="default-mcp-server", version="1.0.0")
    
    # 注册文件系统工具
    server.register_tool(FILESYSTEM_TOOLS[0], read_file_handler)      # read_file
    server.register_tool(FILESYSTEM_TOOLS[1], write_file_handler)     # write_file
    server.register_tool(FILESYSTEM_TOOLS[2], list_directory_handler) # list_directory
    
    # 注册计算工具
    server.register_tool(COMPUTATION_TOOLS[1], math_calculate_handler) # math_calculate
    
    logger.info("默认 MCP Server 创建完成")
    return server
