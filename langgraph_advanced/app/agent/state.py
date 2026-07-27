# -*- coding: utf-8 -*-
"""
Agent 状态定义

状态（State）是 LangGraph 的核心概念之一。
它定义了图中所有节点共享的数据结构。

学习要点：
1. 状态使用 TypedDict 定义，提供类型安全
2. 使用 Annotated 和 add_messages 自动管理消息列表
3. 状态在节点间自动传递和更新
4. 每个节点接收当前状态，返回状态更新
"""

from typing import Annotated, Any, Dict, List, Optional
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


# ============================================================
# 基础 Agent 状态
# ============================================================
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


# ============================================================
# 研究状态（用于子图）
# ============================================================
class ResearchState(TypedDict):
    """
    研究子图状态
    
    用于研究-写作流程中的研究阶段。
    包含研究过程中的中间数据。
    
    学习要点：
    子图可以有独立的状态结构，与主图状态解耦。
    """
    # 对话消息
    messages: Annotated[List[BaseMessage], add_messages]
    
    # 研究查询
    query: str
    
    # 搜索结果
    search_results: List[Dict[str, Any]]
    
    # 分析结果
    analysis: Optional[str]
    
    # 编译后的研究报告
    report: Optional[str]


# ============================================================
# 并行执行状态
# ============================================================
class ParallelState(TypedDict):
    """
    并行执行状态
    
    用于 Fan-out/Fan-in 模式。
    多个 worker 并行执行，然后聚合结果。
    
    学习要点：
    并行执行时，每个 worker 接收相同的输入，
    但返回的结果会被自动合并。
    """
    # 对话消息
    messages: Annotated[List[BaseMessage], add_messages]
    
    # 任务列表（分发给多个 worker）
    tasks: List[str]
    
    # Worker 结果列表
    results: List[Dict[str, Any]]
    
    # 聚合后的最终结果
    aggregated_result: Optional[str]


# ============================================================
# Map-Reduce 状态
# ============================================================
class MapReduceState(TypedDict):
    """
    Map-Reduce 状态
    
    用于处理长文档或大数据集。
    先分片处理（Map），再汇总结果（Reduce）。
    
    学习要点：
    Map-Reduce 是大数据处理的经典模式，
    在 AI Agent 中常用于长文档摘要、批量数据处理等。
    """
    # 对话消息
    messages: Annotated[List[BaseMessage], add_messages]
    
    # 原始文档或数据
    document: str
    
    # 分片后的数据块
    chunks: List[str]
    
    # 每个分片的处理结果
    chunk_results: List[str]
    
    # 汇总后的最终结果
    final_summary: Optional[str]


# ============================================================
# 人机协作状态
# ============================================================
class InterruptState(TypedDict):
    """
    人机协作状态
    
    用于需要人工确认的场景。
    在关键操作前暂停，等待人工输入后恢复。
    
    学习要点：
    使用 LangGraph 的 interrupt 机制实现暂停/恢复。
    状态会被持久化，即使进程重启也能恢复。
    """
    # 对话消息
    messages: Annotated[List[BaseMessage], add_messages]
    
    # 待确认的操作
    pending_action: Optional[Dict[str, Any]]
    
    # 人工反馈
    human_feedback: Optional[str]
    
    # 是否已批准
    approved: bool


# ============================================================
# 多 Agent 状态
# ============================================================
class MultiAgentState(TypedDict):
    """
    多 Agent 协作状态
    
    用于多个 Agent 协同工作的场景。
    包含路由信息和各 Agent 的执行结果。
    
    学习要点：
    多 Agent 系统中，状态需要包含路由信息，
    以便决定下一步交给哪个 Agent 处理。
    """
    # 对话消息
    messages: Annotated[List[BaseMessage], add_messages]
    
    # 当前路由目标
    next_agent: Optional[str]
    
    # 各 Agent 的执行结果
    agent_results: Dict[str, Any]
    
    # 最终结果
    final_result: Optional[str]
