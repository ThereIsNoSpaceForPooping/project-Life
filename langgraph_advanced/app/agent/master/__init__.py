# -*- coding: utf-8 -*-
"""
统一大图（Master Graph）

对外统一从本包导入：
    from app.agent.master import master_graph, build_master_graph

包内职责：
    - state.py : 状态定义（MasterState）+ 结构化输出（TaskAnalysis / ReflectionResult）
    - nodes.py : 所有节点、路由函数、辅助工具
    - graph.py : 图构建与全局实例
"""

from app.agent.master.graph import build_master_graph, master_graph
from app.agent.master.nodes import (
    FORCE_TOOL_KEYWORDS,
    KEEP_RECENT_MESSAGES,
    MAX_CONTEXT_CHARS,
    agent_node,
    auto_explore_node,
    compress_messages_if_needed,
    guard_input_node,
    guard_output_node,
    human_review_node,
    mapreduce_node,
    reflection_node,
    research_subgraph_node,
    route_after_agent,
    route_after_guard_input,
    route_after_human_review,
    route_after_reflection,
    route_after_router,
    route_after_stuck_guard_wrapper,
    router_node,
    subagent_node,
    summarizer_node,
)
from app.agent.master.state import MasterState, ReflectionResult, TaskAnalysis

__all__ = [
    # 状态 + 结构化输出
    "MasterState",
    "TaskAnalysis",
    "ReflectionResult",
    # 节点
    "guard_input_node",
    "router_node",
    "research_subgraph_node",
    "mapreduce_node",
    "subagent_node",
    "agent_node",
    "human_review_node",
    "reflection_node",
    "guard_output_node",
    "summarizer_node",
    "auto_explore_node",
    # 辅助工具
    "compress_messages_if_needed",
    "FORCE_TOOL_KEYWORDS",
    "MAX_CONTEXT_CHARS",
    "KEEP_RECENT_MESSAGES",
    # 路由
    "route_after_guard_input",
    "route_after_router",
    "route_after_agent",
    "route_after_stuck_guard_wrapper",
    "route_after_human_review",
    "route_after_reflection",
    # 图
    "build_master_graph",
    "master_graph",
]
