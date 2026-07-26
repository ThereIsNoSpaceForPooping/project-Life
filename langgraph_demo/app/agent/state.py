# -*- coding: utf-8 -*-
"""
Agent 状态定义

定义 LangGraph 的状态结构
"""

from typing import Annotated, List, Optional
from typing_extensions import TypedDict

from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    """
    Agent 状态定义
    
    Attributes:
        messages: 对话消息列表，使用 add_messages 注解实现自动追加
        conversation_id: 对话 ID，用于记忆隔离
        tool_calls: 工具调用记录
        current_step: 当前执行步骤
    """
    # 消息列表 - 使用 add_messages 实现自动追加新消息
    messages: Annotated[List[BaseMessage], add_messages]
    
    # 对话 ID - 用于记忆隔离
    conversation_id: Optional[str]
    
    # 工具调用记录 - 用于追踪和展示
    tool_calls: Optional[List[dict]]
    
    # 当前步骤 - 用于调试和监控
    current_step: Optional[str]
