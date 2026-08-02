# -*- coding: utf-8 -*-
"""
Agent 图构建

使用 LangGraph 构建智能体执行图。
图（Graph）定义了节点的执行流程和路由逻辑。

学习要点：
1. StateGraph 是 LangGraph 的核心类
2. 使用 add_node() 添加节点
3. 使用 add_edge() 添加固定边
4. 使用 add_conditional_edges() 添加条件边
5. 使用 compile() 编译图，生成可执行的图
"""

from langgraph.graph import StateGraph, END

from app.agent.state import AgentState
from app.agent.nodes import agent_node, tool_node, human_review_node, should_continue, should_review
from app.memory import memory_manager
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def build_agent_graph():
    """
    构建单 Agent 执行图（支持人机协作）
    
    基础模式:
        agent → should_continue → tools → agent（循环）
                    │
                    └→ END
    
    人机协作模式:
        agent → should_review → human_review → tools → agent（循环）
                    │
                    └→ END
    
    这是一个典型的 ReAct 模式：
    - Agent 节点：推理（Thought）
    - 工具节点：行动（Action）
    - 工具结果：观察（Observation）
    - 循环直到 Agent 决定不再调用工具
    
    Returns:
        CompiledGraph: 编译后的 LangGraph 图
    
    学习要点：
    - set_entry_point() 设置入口节点
    - add_conditional_edges() 根据函数返回值路由
    - add_edge() 添加固定边（无条件跳转）
    - compile() 编译图，添加 checkpointer 实现记忆
    - 支持基础模式和人机协作模式切换
    """
    logger.info("构建 Agent 执行图")
    
    # 创建状态图
    workflow = StateGraph(AgentState)
    
    # 添加节点
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)
    
    # 设置入口点
    workflow.set_entry_point("agent")
    
    if settings.ENABLE_HUMAN_REVIEW:
        # ---- 人机协作模式 ----
        logger.info("启用 人机协作 模式（工具调用前需人工确认）")
        
        workflow.add_node("human_review", human_review_node)
        
        # agent → should_review（判断是否需要人工审核）
        workflow.add_conditional_edges(
            "agent",
            should_review,
            {
                "human_review": "human_review",
                "tools": "tools",
                "end": END,
            }
        )
        
        # human_review → tools（人工确认后执行工具）
        workflow.add_edge("human_review", "tools")
    else:
        # ---- 基础模式 ----
        workflow.add_conditional_edges(
            "agent",
            should_continue,
            {
                "tools": "tools",
                "end": END,
            }
        )
    
    # 工具节点执行完后回到 agent（循环）
    workflow.add_edge("tools", "agent")
    
    # 编译图，添加记忆
    # checkpointer 负责持久化状态，实现对话记忆
    graph = workflow.compile(
        checkpointer=memory_manager.checkpointer
    )
    
    logger.info("Agent 执行图构建完成")
    return graph


# 全局单 Agent 图实例
# 在应用启动时创建，所有请求共享同一个图实例
agent_graph = build_agent_graph()
