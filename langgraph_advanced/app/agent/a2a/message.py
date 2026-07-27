# -*- coding: utf-8 -*-
"""
A2A Message 实现

Message 是 A2A 协议中的消息通信模块。
Agent 之间通过 Message 进行通信和协作。

学习要点：
1. Message 是 Agent 间通信的基本单位
2. 支持多种消息类型（请求、响应、通知）
3. 消息包含发送者、接收者、内容、时间戳
4. 支持消息历史和追踪

架构图：
    Agent A                          Agent B
       │                                │
       │── Message (请求) ────────────▶│
       │   (from: A, to: B)             │
       │                                │── 处理请求
       │◀── Message (响应) ────────────│
       │   (from: B, to: A)             │
       │                                │
       │── Message (通知) ────────────▶│
       │   (type: "status_update")      │
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.core.logging import get_logger

logger = get_logger(__name__)


# ============================================================
# 消息类型枚举
# ============================================================
class MessageType(str, Enum):
    """
    消息类型枚举
    
    类型说明：
    - REQUEST: 请求消息（需要响应）
    - RESPONSE: 响应消息（对请求的回复）
    - NOTIFICATION: 通知消息（不需要响应）
    - ERROR: 错误消息
    """
    REQUEST = "request"           # 请求
    RESPONSE = "response"         # 响应
    NOTIFICATION = "notification" # 通知
    ERROR = "error"               # 错误


# ============================================================
# Message 定义
# ============================================================
class Message(BaseModel):
    """
    Message - Agent 间的消息
    
    包含消息的完整信息：
    - 基本信息（ID、类型）
    - 发送者和接收者
    - 消息内容
    - 关联的任务 ID
    - 时间戳
    - 元数据
    
    属性：
        id: 消息唯一标识
        type: 消息类型
        from_agent: 发送者 Agent 名称
        to_agent: 接收者 Agent 名称
        content: 消息内容
        task_id: 关联的任务 ID
        timestamp: 时间戳
        metadata: 额外元数据
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="消息 ID")
    type: MessageType = Field(..., description="消息类型")
    from_agent: str = Field(..., description="发送者 Agent 名称")
    to_agent: str = Field(..., description="接收者 Agent 名称")
    content: Dict[str, Any] = Field(default_factory=dict, description="消息内容")
    task_id: Optional[str] = Field(default=None, description="关联的任务 ID")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="额外元数据")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式
        
        Returns:
            Dict: Message 的字典表示
        """
        return {
            "id": self.id,
            "type": self.type.value,
            "from": self.from_agent,
            "to": self.to_agent,
            "content": self.content,
            "taskId": self.task_id,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


# ============================================================
# 消息工厂
# ============================================================
class MessageFactory:
    """
    消息工厂 - 创建各种类型的消息
    
    提供便捷方法创建不同类型的消息。
    """
    
    @staticmethod
    def create_request(
        from_agent: str,
        to_agent: str,
        content: Dict[str, Any],
        task_id: str = None,
        metadata: Dict[str, Any] = None
    ) -> Message:
        """
        创建请求消息
        
        Args:
            from_agent: 发送者
            to_agent: 接收者
            content: 消息内容
            task_id: 关联的任务 ID
            metadata: 额外元数据
        
        Returns:
            Message: 请求消息
        """
        return Message(
            type=MessageType.REQUEST,
            from_agent=from_agent,
            to_agent=to_agent,
            content=content,
            task_id=task_id,
            metadata=metadata or {}
        )
    
    @staticmethod
    def create_response(
        from_agent: str,
        to_agent: str,
        content: Dict[str, Any],
        task_id: str = None,
        metadata: Dict[str, Any] = None
    ) -> Message:
        """
        创建响应消息
        
        Args:
            from_agent: 发送者
            to_agent: 接收者
            content: 消息内容
            task_id: 关联的任务 ID
            metadata: 额外元数据
        
        Returns:
            Message: 响应消息
        """
        return Message(
            type=MessageType.RESPONSE,
            from_agent=from_agent,
            to_agent=to_agent,
            content=content,
            task_id=task_id,
            metadata=metadata or {}
        )
    
    @staticmethod
    def create_notification(
        from_agent: str,
        to_agent: str,
        content: Dict[str, Any],
        metadata: Dict[str, Any] = None
    ) -> Message:
        """
        创建通知消息
        
        Args:
            from_agent: 发送者
            to_agent: 接收者
            content: 消息内容
            metadata: 额外元数据
        
        Returns:
            Message: 通知消息
        """
        return Message(
            type=MessageType.NOTIFICATION,
            from_agent=from_agent,
            to_agent=to_agent,
            content=content,
            metadata=metadata or {}
        )
    
    @staticmethod
    def create_error(
        from_agent: str,
        to_agent: str,
        error_message: str,
        error_code: str = None,
        task_id: str = None,
        metadata: Dict[str, Any] = None
    ) -> Message:
        """
        创建错误消息
        
        Args:
            from_agent: 发送者
            to_agent: 接收者
            error_message: 错误信息
            error_code: 错误代码
            task_id: 关联的任务 ID
            metadata: 额外元数据
        
        Returns:
            Message: 错误消息
        """
        return Message(
            type=MessageType.ERROR,
            from_agent=from_agent,
            to_agent=to_agent,
            content={
                "error": error_message,
                "code": error_code or "UNKNOWN_ERROR"
            },
            task_id=task_id,
            metadata=metadata or {}
        )


# ============================================================
# 消息历史管理器
# ============================================================
class MessageHistory:
    """
    消息历史管理器
    
    管理 Agent 间的消息历史。
    支持查询、过滤、追踪消息。
    """
    
    def __init__(self):
        """初始化消息历史管理器"""
        self._messages: List[Message] = []
        logger.info("消息历史管理器初始化")
    
    def add_message(self, message: Message):
        """
        添加消息到历史
        
        Args:
            message: 消息实例
        """
        self._messages.append(message)
        logger.debug(f"添加消息: {message.type.value} from {message.from_agent} to {message.to_agent}")
    
    def get_messages(
        self,
        from_agent: str = None,
        to_agent: str = None,
        message_type: MessageType = None,
        task_id: str = None,
        limit: int = 100
    ) -> List[Message]:
        """
        获取消息列表
        
        Args:
            from_agent: 按发送者过滤
            to_agent: 按接收者过滤
            message_type: 按消息类型过滤
            task_id: 按任务 ID 过滤
            limit: 最大返回数量
        
        Returns:
            List[Message]: 消息列表
        """
        messages = self._messages.copy()
        
        # 应用过滤器
        if from_agent:
            messages = [m for m in messages if m.from_agent == from_agent]
        if to_agent:
            messages = [m for m in messages if m.to_agent == to_agent]
        if message_type:
            messages = [m for m in messages if m.type == message_type]
        if task_id:
            messages = [m for m in messages if m.task_id == task_id]
        
        # 按时间倒序
        messages.sort(key=lambda m: m.timestamp, reverse=True)
        
        # 限制数量
        return messages[:limit]
    
    def get_conversation(
        self,
        agent_a: str,
        agent_b: str,
        limit: int = 100
    ) -> List[Message]:
        """
        获取两个 Agent 之间的对话
        
        Args:
            agent_a: Agent A 名称
            agent_b: Agent B 名称
            limit: 最大返回数量
        
        Returns:
            List[Message]: 对话消息列表
        """
        messages = [
            m for m in self._messages
            if (m.from_agent == agent_a and m.to_agent == agent_b) or
               (m.from_agent == agent_b and m.to_agent == agent_a)
        ]
        
        # 按时间正序
        messages.sort(key=lambda m: m.timestamp)
        
        return messages[:limit]
    
    def clear(self):
        """清空消息历史"""
        self._messages.clear()
        logger.info("清空消息历史")


# 全局消息历史
message_history = MessageHistory()
