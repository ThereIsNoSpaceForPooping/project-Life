# -*- coding: utf-8 -*-
"""
Agent 图构建

使用 LangGraph 构建智能体执行图
支持两种模式：
  - 单 Agent 模式：基础推理 + 工具调用
  - 人机协作模式：工具调用前暂停等待人工确认
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

    Returns:
        CompiledGraph: 编译后的 LangGraph 图
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
    graph = workflow.compile(
        checkpointer=memory_manager.checkpointer
    )

    logger.info("Agent 执行图构建完成")
    return graph


# 全局单 Agent 图实例
agent_graph = build_agent_graph()
