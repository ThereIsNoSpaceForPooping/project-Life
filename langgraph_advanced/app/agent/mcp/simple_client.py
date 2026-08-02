# -*- coding: utf-8 -*-
"""
MCP Client - 连接独立 MCP Server

这是一个简化的 MCP 客户端，用于连接独立的 mcp_server 服务。
使用 HTTP REST API 进行通信。

架构：
    主智能体 (8000) → MCP Client → HTTP → MCP Server (8001)
"""

import httpx
from typing import Any, Dict, List, Optional
from app.core.logging import get_logger

logger = get_logger(__name__)


class SimpleMCPClient:
    """
    简化的 MCP 客户端
    
    用于连接独立的 mcp_server 服务。
    """
    
    def __init__(self, base_url: str = "http://localhost:8001"):
        """
        初始化客户端
        
        Args:
            base_url: MCP Server 的 URL
        """
        self.base_url = base_url.rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None
        logger.info(f"MCP Client 初始化: {base_url}")
    
    async def connect(self) -> None:
        """建立连接"""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
            logger.info("MCP Client 连接已建立")
    
    async def disconnect(self) -> None:
        """断开连接"""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("MCP Client 连接已断开")
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """
        获取可用工具列表
        
        Returns:
            工具列表
        """
        if not self._client:
            await self.connect()
        
        try:
            response = await self._client.get(f"{self.base_url}/mcp/tools/list")
            response.raise_for_status()
            tools = response.json()
            logger.info(f"获取到 {len(tools)} 个 MCP 工具")
            return tools
        except Exception as e:
            logger.error(f"获取工具列表失败: {e}")
            return []
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        调用工具
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
        
        Returns:
            工具执行结果
        """
        if not self._client:
            await self.connect()
        
        try:
            response = await self._client.post(
                f"{self.base_url}/mcp/tools/call",
                json={
                    "tool_name": tool_name,
                    "arguments": arguments
                }
            )
            response.raise_for_status()
            result = response.json()
            
            if result.get("is_error"):
                logger.error(f"工具调用失败: {result.get('result')}")
                return {"error": result.get("result")}
            
            logger.info(f"工具 {tool_name} 调用成功")
            return result.get("result")
        
        except Exception as e:
            logger.error(f"调用工具 {tool_name} 失败: {e}")
            return {"error": str(e)}
    
    async def health_check(self) -> bool:
        """
        健康检查
        
        Returns:
            服务是否健康
        """
        if not self._client:
            await self.connect()
        
        try:
            response = await self._client.get(f"{self.base_url}/health")
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"MCP Server 健康检查失败: {e}")
            return False


# 全局客户端实例
mcp_client = SimpleMCPClient()
