# -*- coding: utf-8 -*-
"""
Agent 图构建

使用 LangGraph 构建智能体执行图
"""

from langgraph.graph import StateGraph, END

from app.agent.state import AgentState
from app.agent.nodes import agent_node, tool_node, should_continue
from app.memory import memory_manager
from app.core.logging import get_logger

logger = get_logger(__name__)


def build_agent_graph():
    """
    构建 Agent 执行图
    
    图结构:
        agent -> (判断) -> tools -> agent
                  |
                  v
                 END
    
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
    
    # 添加条件边：agent 节点后判断是否继续
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "end": END,
        }
    )
    
    # 工具节点执行完后回到 agent
    workflow.add_edge("tools", "agent")
    
    # 编译图，添加记忆
    graph = workflow.compile(
        checkpointer=memory_manager.checkpointer
    )
    
    logger.info("Agent 执行图构建完成")
    return graph


# 全局图实例
agent_graph = build_agent_graph()
