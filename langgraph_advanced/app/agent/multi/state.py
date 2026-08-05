# -*- coding: utf-8 -*-
"""
多 Agent 协作图 —— 状态定义

本模块定义多 Agent 协作图（multi graph）所使用的 State（TypedDict）。

设计说明：
    - 状态在节点之间共享，由 LangGraph 在每一步自动注入与更新。
    - 节点函数返回 dict，仅写"差异字段"，LangGraph 会合并到当前 State。
    - messages 使用 add_messages 注解，确保新消息追加到列表末尾（不会覆盖）。

字段约定：
    - messages：消息历史（必填，LangGraph 自动追加）
    - next_agent：路由器写入的下一跳 Agent 名称（researcher / coder / summarizer）
    - final_result：总结 Agent 写入的最终结果（供 API 层直接读取，避免遍历 messages）

学习要点：
    - 多 Agent 系统的 State 必须包含"路由信息"，由条件边根据该字段决定下一步。
    - 每个专业 Agent 通常只往 messages 追加结果，由 summarizer 统一收口。
"""

from typing import Annotated, List, Optional

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class MultiAgentState(TypedDict):
    """
    多 Agent 协作图状态

    Attributes:
        messages: 对话消息列表（LangGraph 自动追加；add_messages 保证不会覆盖）。
        next_agent: 路由器决策的下一个 Agent 名称（researcher/coder/summarizer）。
        final_result: 总结 Agent 写入的最终回复（避免调用方遍历 messages 拼接）。
    """

    # ------------------------------------------------------------------
    # 消息历史：使用 add_messages 注解实现自动追加语义
    # ------------------------------------------------------------------
    messages: Annotated[List[BaseMessage], add_messages]

    # ------------------------------------------------------------------
    # 路由决策：路由器节点写入，条件边读取
    # ------------------------------------------------------------------
    next_agent: Optional[str]

    # ------------------------------------------------------------------
    # 最终结果：由 summarizer 节点填充，供 API 层直接返回
    # ------------------------------------------------------------------
    final_result: Optional[str]
