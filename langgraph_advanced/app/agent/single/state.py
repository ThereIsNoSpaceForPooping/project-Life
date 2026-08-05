# -*- coding: utf-8 -*-
"""
单 Agent 状态定义

最简单的 Agent 状态结构，用于 ReAct 模式（推理-行动-观察循环）。
"""

from typing import Annotated, Any, Dict, List, Optional
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """
    基础 Agent 状态

    这是最简单的状态结构，包含：
    - messages: 对话消息列表（自动追加，不会覆盖）
    - tool_calls: 工具调用记录
    - current_step: 当前执行步骤
    - next_agent: 下一个要执行的 Agent（多 Agent 场景）
    - final_result: 最终结果

    使用示例：
        state = {
            "messages": [HumanMessage(content="你好")],
            "tool_calls": [],
            "current_step": "agent",
        }
    """
    # 消息列表 - 使用 add_messages 注解
    # add_messages 确保新消息追加到列表末尾，而不是覆盖
    messages: Annotated[List[BaseMessage], add_messages]

    # 工具调用记录
    tool_calls: List[Dict[str, Any]]

    # 当前执行步骤（用于调试和追踪）
    current_step: str

    # 下一个要执行的 Agent（多 Agent 场景）
    next_agent: Optional[str]

    # 最终结果
    final_result: Optional[str]
