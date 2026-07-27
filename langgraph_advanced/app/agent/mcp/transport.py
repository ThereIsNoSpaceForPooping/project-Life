# -*- coding: utf-8 -*-
"""
MCP 传输层实现

MCP（Model Context Protocol）支持多种传输方式：
1. stdio - 标准输入输出（本地进程通信）
2. SSE - Server-Sent Events（HTTP 流式）
3. HTTP - 标准 HTTP 请求

学习要点：
1. Transport 是 MCP 的通信基础设施
2. 不同传输方式适用于不同场景
3. stdio 适合本地工具
4. SSE 适合远程服务
5. HTTP 适合简单请求-响应
"""

import asyncio
import json
from typing import Any, Dict, Optional
from abc import ABC, abstractmethod

from app.core.logging import get_logger

logger = get_logger(__name__)


# ============================================================
# 传输层基类
# ============================================================
class BaseTransport(ABC):
    """
    传输层基类
    
    所有 MCP 传输方式都必须实现这个接口。
    定义了发送和接收消息的标准方法。
    """
    
    @abstractmethod
    async def send(self, message: Dict[str, Any]) -> None:
        """发送消息"""
        pass
    
    @abstractmethod
    async def receive(self) -> Optional[Dict[str, Any]]:
        """接收消息"""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """关闭连接"""
        pass


# ============================================================
# stdio 传输层
# ============================================================
class StdioTransport(BaseTransport):
    """
    stdio 传输层 - 标准输入输出
    
    适用场景：
    - 本地 MCP Server（子进程）
    - 命令行工具
    - 开发调试
    
    工作原理：
    1. 父进程启动子进程作为 MCP Server
    2. 通过 stdin/stdout 进行 JSON-RPC 通信
    3. 每行一个 JSON 消息
    
    架构图：
        父进程                    子进程（MCP Server）
           │                           │
           │── stdin (JSON) ──────────▶│
           │                           │── 处理请求
           │◀── stdout (JSON) ─────────│
           │                           │
    """
    
    def __init__(self, process: asyncio.subprocess.Process):
        """
        初始化 stdio 传输层
        
        Args:
            process: 子进程实例
        """
        self.process = process
        self._closed = False
        logger.info("stdio 传输层初始化完成")
    
    async def send(self, message: Dict[str, Any]) -> None:
        """
        发送消息到子进程 stdin
        
        Args:
            message: JSON-RPC 消息
        """
        if self._closed:
            raise RuntimeError("传输层已关闭")
        
        # 序列化为 JSON 并添加换行符
        json_str = json.dumps(message, ensure_ascii=False) + "\n"
        
        # 写入子进程 stdin
        self.process.stdin.write(json_str.encode("utf-8"))
        await self.process.stdin.drain()
        
        logger.debug(f"发送消息: {message.get('method', 'unknown')}")
    
    async def receive(self) -> Optional[Dict[str, Any]]:
        """
        从子进程 stdout 接收消息
        
        Returns:
            Dict: JSON-RPC 消息，如果 EOF 则返回 None
        """
        if self._closed:
            return None
        
        # 读取一行
        line = await self.process.stdout.readline()
        
        if not line:
            # EOF
            return None
        
        # 解析 JSON
        try:
            message = json.loads(line.decode("utf-8").strip())
            logger.debug(f"接收消息: {message.get('method', 'unknown')}")
            return message
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}")
            return None
    
    async def close(self) -> None:
        """关闭子进程"""
        if not self._closed:
            self._closed = True
            self.process.stdin.close()
            self.process.terminate()
            await self.process.wait()
            logger.info("stdio 传输层已关闭")


# ============================================================
# SSE 传输层
# ============================================================
class SSETransport(BaseTransport):
    """
    SSE 传输层 - Server-Sent Events
    
    适用场景：
    - 远程 MCP Server
    - Web 应用
    - 需要流式响应的场景
    
    工作原理：
    1. 客户端通过 HTTP POST 发送请求
    2. 服务端通过 SSE 流式返回响应
    3. 支持双向通信
    
    架构图：
        客户端                          服务端（MCP Server）
           │                                │
           │── HTTP POST (JSON) ───────────▶│
           │                                │── 处理请求
           │◀── SSE Stream ────────────────│
           │    data: {...}\n\n             │
           │    data: {...}\n\n             │
           │    data: [DONE]\n\n            │
    """
    
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        """
        初始化 SSE 传输层
        
        Args:
            base_url: MCP Server 的 URL
            api_key: API 密钥（可选）
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._session = None
        self._closed = False
        logger.info(f"SSE 传输层初始化: {base_url}")
    
    async def _get_session(self):
        """获取 HTTP 会话（懒加载）"""
        if self._session is None:
            import httpx
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._session = httpx.AsyncClient(headers=headers, timeout=30.0)
        return self._session
    
    async def send(self, message: Dict[str, Any]) -> None:
        """
        发送消息到 MCP Server
        
        Args:
            message: JSON-RPC 消息
        """
        if self._closed:
            raise RuntimeError("传输层已关闭")
        
        session = await self._get_session()
        
        # 发送 POST 请求
        response = await session.post(
            f"{self.base_url}/message",
            json=message
        )
        response.raise_for_status()
        
        logger.debug(f"发送消息: {message.get('method', 'unknown')}")
    
    async def receive(self) -> Optional[Dict[str, Any]]:
        """
        从 MCP Server 接收消息（SSE 流式）
        
        Returns:
            Dict: JSON-RPC 消息
        """
        if self._closed:
            return None
        
        session = await self._get_session()
        
        # 发送 SSE 请求
        async with session.stream(
            "GET",
            f"{self.base_url}/events"
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]  # 去掉 "data: " 前缀
                    
                    if data == "[DONE]":
                        return None
                    
                    try:
                        message = json.loads(data)
                        logger.debug(f"接收消息: {message.get('method', 'unknown')}")
                        return message
                    except json.JSONDecodeError:
                        continue
        
        return None
    
    async def close(self) -> None:
        """关闭 HTTP 会话"""
        if not self._closed:
            self._closed = True
            if self._session:
                await self._session.aclose()
            logger.info("SSE 传输层已关闭")


# ============================================================
# HTTP 传输层
# ============================================================
class HTTPTransport(BaseTransport):
    """
    HTTP 传输层 - 标准 HTTP 请求
    
    适用场景：
    - 简单的请求-响应场景
    - 不需要流式响应
    - RESTful API 风格
    
    工作原理：
    1. 客户端发送 HTTP POST 请求
    2. 服务端处理并返回 JSON 响应
    3. 一次性返回完整结果
    
    架构图：
        客户端                          服务端（MCP Server）
           │                                │
           │── HTTP POST (JSON) ───────────▶│
           │                                │── 处理请求
           │◀── HTTP Response (JSON) ──────│
    """
    
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        """
        初始化 HTTP 传输层
        
        Args:
            base_url: MCP Server 的 URL
            api_key: API 密钥（可选）
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._session = None
        self._closed = False
        self._response_queue = asyncio.Queue()
        logger.info(f"HTTP 传输层初始化: {base_url}")
    
    async def _get_session(self):
        """获取 HTTP 会话"""
        if self._session is None:
            import httpx
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._session = httpx.AsyncClient(headers=headers, timeout=30.0)
        return self._session
    
    async def send(self, message: Dict[str, Any]) -> None:
        """
        发送消息到 MCP Server
        
        Args:
            message: JSON-RPC 消息
        """
        if self._closed:
            raise RuntimeError("传输层已关闭")
        
        session = await self._get_session()
        
        # 发送 POST 请求
        response = await session.post(
            f"{self.base_url}/rpc",
            json=message
        )
        response.raise_for_status()
        
        # 将响应放入队列
        result = response.json()
        await self._response_queue.put(result)
        
        logger.debug(f"发送消息: {message.get('method', 'unknown')}")
    
    async def receive(self) -> Optional[Dict[str, Any]]:
        """
        从队列中接收响应
        
        Returns:
            Dict: JSON-RPC 响应
        """
        if self._closed:
            return None
        
        try:
            # 从队列中获取响应（带超时）
            message = await asyncio.wait_for(
                self._response_queue.get(),
                timeout=30.0
            )
            logger.debug(f"接收消息: {message.get('method', 'unknown')}")
            return message
        except asyncio.TimeoutError:
            logger.warning("接收消息超时")
            return None
    
    async def close(self) -> None:
        """关闭 HTTP 会话"""
        if not self._closed:
            self._closed = True
            if self._session:
                await self._session.aclose()
            logger.info("HTTP 传输层已关闭")


# ============================================================
# 传输层工厂
# ============================================================
def create_transport(
    transport_type: str,
    **kwargs
) -> BaseTransport:
    """
    创建传输层实例
    
    Args:
        transport_type: 传输类型（stdio / sse / http）
        **kwargs: 传输层参数
    
    Returns:
        BaseTransport: 传输层实例
    
    使用示例：
        # stdio 传输
        transport = create_transport("stdio", process=process)
        
        # SSE 传输
        transport = create_transport("sse", base_url="http://localhost:8080")
        
        # HTTP 传输
        transport = create_transport("http", base_url="http://localhost:8080")
    """
    if transport_type == "stdio":
        return StdioTransport(**kwargs)
    elif transport_type == "sse":
        return SSETransport(**kwargs)
    elif transport_type == "http":
        return HTTPTransport(**kwargs)
    else:
        raise ValueError(f"不支持的传输类型: {transport_type}")
