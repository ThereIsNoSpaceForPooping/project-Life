# -*- coding: utf-8 -*-
"""
A2A Client - 连接独立 A2A Server

这是一个简化的 A2A 客户端，用于连接独立的 a2a_server 服务。
使用 HTTP REST API 进行通信。

架构：
    主智能体 (8000) → A2A Client → HTTP → A2A Server (8002)
"""

import httpx
from typing import Any, Dict, List, Optional
from app.core.logging import get_logger

logger = get_logger(__name__)


class SimpleA2AClient:
    """
    简化的 A2A 客户端
    
    用于连接独立的 a2a_server 服务。
    """
    
    def __init__(self, base_url: str = "http://localhost:8002"):
        """
        初始化客户端
        
        Args:
            base_url: A2A Server 的 URL
        """
        self.base_url = base_url.rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None
        logger.info(f"A2A Client 初始化: {base_url}")
    
    async def connect(self) -> None:
        """建立连接"""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0)
            logger.info("A2A Client 连接已建立")
    
    async def disconnect(self) -> None:
        """断开连接"""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("A2A Client 连接已断开")
    
    async def list_agents(self) -> List[Dict[str, Any]]:
        """
        获取可用 Agent 列表
        
        Returns:
            Agent 列表
        """
        if not self._client:
            await self.connect()
        
        try:
            response = await self._client.get(f"{self.base_url}/a2a/agents")
            response.raise_for_status()
            agents = response.json()
            logger.info(f"获取到 {len(agents)} 个 A2A Agent")
            return agents
        except Exception as e:
            logger.error(f"获取 Agent 列表失败: {e}")
            return []
    
    async def create_task(
        self,
        agent_name: str,
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        创建任务
        
        Args:
            agent_name: Agent 名称
            input_data: 输入数据
        
        Returns:
            任务结果
        """
        if not self._client:
            await self.connect()
        
        try:
            response = await self._client.post(
                f"{self.base_url}/a2a/tasks",
                json={
                    "agent_name": agent_name,
                    "input_data": input_data
                }
            )
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"任务创建成功: {result.get('task_id')}")
            return result
        
        except Exception as e:
            logger.error(f"创建任务失败: {e}")
            return {"error": str(e), "status": "failed"}
    
    async def get_task(self, task_id: str) -> Dict[str, Any]:
        """
        获取任务状态
        
        Args:
            task_id: 任务 ID
        
        Returns:
            任务信息
        """
        if not self._client:
            await self.connect()
        
        try:
            response = await self._client.get(f"{self.base_url}/a2a/tasks/{task_id}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"获取任务 {task_id} 失败: {e}")
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
            logger.error(f"A2A Server 健康检查失败: {e}")
            return False


# 全局客户端实例
a2a_client = SimpleA2AClient()
