# -*- coding: utf-8 -*-
"""
MCP Client 实现

MCP Client 是连接到 MCP Server 的客户端。
Agent 通过 Client 调用 Server 提供的工具。

学习要点：
1. Client 通过传输层连接到 Server
2. 使用 JSON-RPC 2.0 协议通信
3. Client 负责序列化工具调用和反序列化结果
4. 支持异步调用

架构图：
    Agent → MCP Client → Transport → MCP Server → Tool Handler
                ↑                                    ↓
                └────── Transport ←── JSON-RPC ──────┘
"""

import asyncio
from typing import Any, Dict, List, Optional

from app.agent.mcp.transport import BaseTransport, create_transport
from app.agent.mcp.tools import MCPToolDefinition
from app.core.logging import get_logger

logger = get_logger(__name__)


# ============================================================
# MCP Client 类
# ============================================================
class MCPClient:
    """
    MCP Client - 连接到 MCP Server 的客户端
    
    职责：
    1. 通过传输层连接到 Server
    2. 获取可用工具列表
    3. 调用工具并获取结果
    4. 管理连接生命周期
    
    使用示例：
        client = MCPClient()
        await client.connect("stdio", process=process)
        tools = await client.list_tools()
        result = await client.call_tool("read_file", {"path": "/tmp/test.txt"})
        await client.disconnect()
    """
    
    def __init__(self):
        """初始化 MCP Client"""
        self._transport: Optional[BaseTransport] = None
        self._request_id = 0
        self._connected = False
        self._server_info: Optional[Dict] = None
        
        logger.info("MCP Client 初始化")
    
    async def connect(self, transport_type: str, **kwargs) -> None:
        """
        连接到 MCP Server
        
        Args:
            transport_type: 传输类型（stdio / sse / http）
            **kwargs: 传输层参数
        
        使用示例：
            # stdio 连接
            await client.connect("stdio", process=subprocess)
            
            # HTTP 连接
            await client.connect("http", base_url="http://localhost:8080")
        """
        if self._connected:
            logger.warning("Client 已连接")
            return
        
        # 创建传输层
        self._transport = create_transport(transport_type, **kwargs)
        
        # 发送 initialize 请求
        init_result = await self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "langgraph-mcp-client",
                "version": "1.0.0",
            }
        })
        
        self._server_info = init_result
        self._connected = True
        
        logger.info(f"连接到 MCP Server: {init_result.get('serverInfo', {})}")
    
    async def disconnect(self) -> None:
        """断开连接"""
        if not self._connected:
            return
        
        if self._transport:
            await self._transport.close()
        
        self._connected = False
        self._transport = None
        self._server_info = None
        
        logger.info("从 MCP Server 断开连接")
    
    async def _send_request(self, method: str, params: Dict = None) -> Dict:
        """
        发送 JSON-RPC 请求
        
        Args:
            method: 方法名
            params: 参数
        
        Returns:
            Dict: 响应结果
        """
        if not self._connected or not self._transport:
            raise RuntimeError("Client 未连接")
        
        # 生成请求 ID
        self._request_id += 1
        request_id = self._request_id
        
        # 构造 JSON-RPC 请求
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": request_id,
        }
        
        logger.debug(f"发送请求: {method}, id={request_id}")
        
        # 发送请求
        await self._transport.send(request)
        
        # 接收响应
        response = await self._transport.receive()
        
        if response is None:
            raise RuntimeError("未收到响应")
        
        # 检查错误
        if "error" in response:
            error = response["error"]
            raise RuntimeError(f"JSON-RPC 错误: {error.get('message', '未知错误')}")
        
        # 返回结果
        return response.get("result", {})
    
    async def list_tools(self) -> List[MCPToolDefinition]:
        """
        获取可用工具列表
        
        Returns:
            List[MCPToolDefinition]: 工具定义列表
        
        使用示例：
            tools = await client.list_tools()
            for tool in tools:
                print(f"{tool.name}: {tool.description}")
        """
        result = await self._send_request("tools/list")
        
        tools_data = result.get("tools", [])
        tools = []
        
        for tool_data in tools_data:
            tool = MCPToolDefinition(
                name=tool_data["name"],
                description=tool_data["description"],
                parameters=tool_data.get("inputSchema", {}),
                required=tool_data.get("inputSchema", {}).get("required", [])
            )
            tools.append(tool)
        
        logger.info(f"获取到 {len(tools)} 个工具")
        return tools
    
    async def call_tool(self, tool_name: str, arguments: Dict = None) -> Any:
        """
        调用工具
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
        
        Returns:
            Any: 工具执行结果
        
        使用示例：
            result = await client.call_tool("read_file", {"path": "/tmp/test.txt"})
            print(result)
        """
        logger.info(f"调用工具: {tool_name}, 参数: {arguments}")
        
        result = await self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments or {},
        })
        
        # 提取结果内容
        content = result.get("content", [])
        is_error = result.get("isError", False)
        
        if is_error:
            error_text = content[0].get("text", "未知错误") if content else "未知错误"
            raise RuntimeError(f"工具调用失败: {error_text}")
        
        # 返回文本内容
        if content and content[0].get("type") == "text":
            return content[0].get("text", "")
        
        return result
    
    async def ping(self) -> bool:
        """
        测试连接
        
        Returns:
            bool: 连接是否正常
        """
        try:
            await self._send_request("ping")
            return True
        except Exception as e:
            logger.error(f"Ping 失败: {e}")
            return False
    
    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        return self._connected
    
    @property
    def server_info(self) -> Optional[Dict]:
        """Server 信息"""
        return self._server_info


# ============================================================
# MCP 工具包装器
# ============================================================
class MCPToolWrapper:
    """
    MCP 工具包装器 - 将 MCP 工具转换为 LangChain 工具
    
    这样可以让 Agent 像使用普通 LangChain 工具一样使用 MCP 工具。
    
    使用示例：
        wrapper = MCPToolWrapper(client)
        langchain_tools = await wrapper.get_langchain_tools()
        llm_with_tools = llm.bind_tools(langchain_tools)
    """
    
    def __init__(self, client: MCPClient):
        """
        初始化包装器
        
        Args:
            client: MCP Client 实例
        """
        self.client = client
    
    async def get_langchain_tools(self) -> list:
        """
        获取 LangChain 格式的工具列表
        
        Returns:
            list: LangChain 工具列表
        """
        from langchain_core.tools import StructuredTool
        from pydantic import create_model
        
        mcp_tools = await self.client.list_tools()
        langchain_tools = []
        
        for mcp_tool in mcp_tools:
            # 动态创建 Pydantic 模型
            properties = mcp_tool.parameters.get("properties", {})
            required = mcp_tool.parameters.get("required", [])
            
            # 构造字段定义
            fields = {}
            for field_name, field_schema in properties.items():
                field_type = self._json_type_to_python(field_schema.get("type", "string"))
                field_desc = field_schema.get("description", "")
                
                if field_name in required:
                    fields[field_name] = (field_type, ...)
                else:
                    fields[field_name] = (Optional[field_type], None)
            
            # 创建动态模型
            model_name = f"{mcp_tool.name}_Input"
            input_model = create_model(model_name, **fields)
            
            # 创建异步调用函数
            async def tool_func(**kwargs):
                return await self.client.call_tool(mcp_tool.name, kwargs)
            
            # 创建 LangChain 工具
            tool = StructuredTool(
                name=mcp_tool.name,
                description=mcp_tool.description,
                coroutine=tool_func,
                args_schema=input_model,
            )
            
            langchain_tools.append(tool)
        
        logger.info(f"转换 {len(langchain_tools)} 个 MCP 工具为 LangChain 格式")
        return langchain_tools
    
    def _json_type_to_python(self, json_type: str) -> type:
        """
        将 JSON Schema 类型转换为 Python 类型
        
        Args:
            json_type: JSON 类型（string / number / integer / boolean / array / object）
        
        Returns:
            type: Python 类型
        """
        type_map = {
            "string": str,
            "number": float,
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        return type_map.get(json_type, str)


# ============================================================
# 便捷函数
# ============================================================
async def create_mcp_client(
    transport_type: str = "http",
    **kwargs
) -> MCPClient:
    """
    创建并连接 MCP Client
    
    Args:
        transport_type: 传输类型
        **kwargs: 传输层参数
    
    Returns:
        MCPClient: 已连接的 Client 实例
    
    使用示例：
        client = await create_mcp_client("http", base_url="http://localhost:8080")
        tools = await client.list_tools()
        await client.disconnect()
    """
    client = MCPClient()
    await client.connect(transport_type, **kwargs)
    return client
