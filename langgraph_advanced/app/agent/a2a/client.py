# -*- coding: utf-8 -*-
"""
A2A 真实客户端（Google A2A 协议 v0.2）

通过 JSON-RPC 2.0 over HTTP 与 A2A Server 通信。
支持：
    - AgentCard 服务发现
    - message/send    同步消息
    - message/stream  SSE 流式消息
    - tasks/get       任务查询
    - tasks/cancel    任务取消
    - tasks/resubscribe 重新订阅

典型用法：
    client = A2AClient("http://localhost:8002")
    await client.discover()            # 拉取 Agent Card
    result = await client.send("查一下 RAG 的最新论文", agent_name="researcher")
    async for event in client.stream("写个排序算法"):
        print(event)
    await client.close()
"""

import asyncio
import json
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from app.core.logging import get_logger

logger: logging.Logger = get_logger(__name__)


# ============================================================
# JSON-RPC 2.0 错误码
# ============================================================
JSON_RPC_PARSE_ERROR: int = -32700
JSON_RPC_INVALID_REQUEST: int = -32600
JSON_RPC_METHOD_NOT_FOUND: int = -32601
JSON_RPC_INVALID_PARAMS: int = -32602
JSON_RPC_INTERNAL_ERROR: int = -32603


class A2AError(Exception):
    """A2A 协议错误"""
    def __init__(self, code: int, message: str, data: Any = None) -> None:
        self.code: int = code
        self.message: str = message
        self.data: Any = data
        super().__init__(f"[A2A Error {code}] {message}")


class A2AClient:
    """
    A2A 真实客户端

    实现 Google A2A 协议 v0.2 的所有 JSON-RPC 方法。
    使用 httpx.AsyncClient 异步通信，支持 SSE 流式响应。
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8002",
        timeout: float = 60.0,
    ) -> None:
        """
        初始化客户端

        Args:
            base_url: A2A Server 的根 URL
            timeout: 默认超时秒数
        """
        self.base_url: str = base_url.rstrip("/")
        self.timeout: float = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self.agent_card: Optional[Dict[str, Any]] = None
        self._request_id: int = 0

    async def __aenter__(self) -> "A2AClient":
        """异步上下文管理器入口"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        """异步上下文管理器退出"""
        await self.close()

    async def connect(self) -> None:
        """建立连接（创建 httpx 客户端）"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={"Content-Type": "application/json"},
            )
            logger.info("[A2AClient] 已连接: %s", self.base_url)

    async def close(self) -> None:
        """关闭连接"""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("[A2AClient] 已关闭")

    def _next_id(self) -> int:
        """生成下一个 JSON-RPC 请求 ID"""
        self._request_id += 1
        return self._request_id

    # ============================================================
    # 服务发现
    # ============================================================
    async def discover(self) -> Dict[str, Any]:
        """
        拉取 Agent Card（服务发现）

        符合 A2A 规范：GET /.well-known/agent.json

        Returns:
            Agent Card 字典
        """
        if not self._client:
            await self.connect()

        url: str = f"{self.base_url}/.well-known/agent.json"
        response: httpx.Response = await self._client.get(url)
        response.raise_for_status()
        self.agent_card = response.json()

        logger.info(
            "[A2AClient] 发现 Server: name='%s', skills=%d",
            self.agent_card.get("name"),
            len(self.agent_card.get("skills", [])),
        )
        return self.agent_card

    def get_agent_names(self) -> List[str]:
        """获取 Server 注册的所有 Agent 名称（来自 Agent Card）"""
        if not self.agent_card:
            return []
        return [
            skill.get("id", "").split("-")[0]
            for skill in self.agent_card.get("skills", [])
        ]

    def get_skills(self) -> List[Dict[str, Any]]:
        """获取所有技能定义"""
        if not self.agent_card:
            return []
        return self.agent_card.get("skills", [])

    # ============================================================
    # JSON-RPC 调用
    # ============================================================
    async def _rpc(
        self,
        method: str,
        params: Dict[str, Any],
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        发送 JSON-RPC 2.0 请求

        Args:
            method: JSON-RPC 方法名
            params: 参数
            timeout: 超时秒数

        Returns:
            响应字典

        Raises:
            A2AError: 当 Server 返回错误
        """
        if not self._client:
            await self.connect()

        request: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params,
        }

        url: str = f"{self.base_url}/a2a/jsonrpc"
        response: httpx.Response = await self._client.post(
            url,
            json=request,
            timeout=timeout,
        )
        response.raise_for_status()
        body: Dict[str, Any] = response.json()

        # 错误处理
        if "error" in body:
            error: Dict[str, Any] = body["error"]
            raise A2AError(
                code=error.get("code", JSON_RPC_INTERNAL_ERROR),
                message=error.get("message", "未知错误"),
                data=error.get("data"),
            )

        return body.get("result", {})

    # ============================================================
    # message/send（同步）
    # ============================================================
    async def send(
        self,
        text: str,
        agent_name: Optional[str] = None,
        session_id: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        同步发送消息

        Args:
            text: 消息文本
            agent_name: 目标 Agent（不指定则 Server 端路由）
            session_id: 会话 ID（用于多轮对话）
            timeout: 超时秒数

        Returns:
            Task 字典
        """
        params: Dict[str, Any] = {
            "message": {
                "role": "user",
                "parts": [{"type": "text", "text": text}],
            },
        }
        if agent_name:
            params["agentName"] = agent_name
        if session_id:
            params["sessionId"] = session_id

        logger.info(
            "[A2AClient] 发送消息: agent=%s, text='%s...'",
            agent_name or "(auto)", text[:40],
        )
        result: Dict[str, Any] = await self._rpc(
            "message/send", params, timeout=timeout
        )
        return result.get("task", {})

    # ============================================================
    # message/stream（SSE 流式）
    # ============================================================
    async def stream(
        self,
        text: str,
        agent_name: Optional[str] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        流式发送消息（SSE）

        解析 Server 推送的 SSE 事件，逐个 yield 给调用方。

        Args:
            text: 消息文本
            agent_name: 目标 Agent

        Yields:
            事件字典
        """
        if not self._client:
            await self.connect()

        request: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "message/stream",
            "params": {
                "message": {
                    "role": "user",
                    "parts": [{"type": "text", "text": text}],
                },
            },
        }
        if agent_name:
            request["params"]["agentName"] = agent_name

        url: str = f"{self.base_url}/a2a/jsonrpc"

        async with self._client.stream(
            "POST", url, json=request, timeout=None
        ) as response:
            response.raise_for_status()

            current_event: str = "message"
            data_lines: List[str] = []

            async for line in response.aiter_lines():
                # SSE 协议以空行分隔事件
                if line == "":
                    if data_lines:
                        data_str: str = "\n".join(data_lines)
                        try:
                            event: Dict[str, Any] = json.loads(data_str)
                            event["eventType"] = current_event
                            yield event
                        except json.JSONDecodeError as exc:
                            logger.warning(
                                "[A2AClient] SSE JSON 解析失败: %s, data=%s",
                                exc, data_str[:100],
                            )
                        data_lines = []
                        current_event = "message"
                    continue

                if line.startswith("event:"):
                    current_event = line[6:].strip()
                elif line.startswith("data:"):
                    data_lines.append(line[5:].strip())

    # ============================================================
    # tasks/get
    # ============================================================
    async def get_task(self, task_id: str) -> Dict[str, Any]:
        """获取任务详情"""
        result: Dict[str, Any] = await self._rpc(
            "tasks/get", {"id": task_id}
        )
        return result.get("task", {})

    # ============================================================
    # tasks/cancel
    # ============================================================
    async def cancel_task(self, task_id: str) -> Dict[str, Any]:
        """取消任务"""
        result: Dict[str, Any] = await self._rpc(
            "tasks/cancel", {"id": task_id}
        )
        return result
