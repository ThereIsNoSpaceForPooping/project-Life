# -*- coding: utf-8 -*-
"""
多 Agent 协作图（multi graph）

对外统一从本包导入：
    from app.agent.multi import multi_agent_graph, build_multi_agent_graph

包内职责：
    - state.py  : 状态定义（MultiAgentState）
    - nodes.py  : 节点与路由函数（router / researcher / coder / summarizer）
    - graph.py  : 图构建与全局实例
"""

from app.agent.multi.graph import build_multi_agent_graph, multi_agent_graph
from app.agent.multi.nodes import (
    coder_node,
    researcher_node,
    route_to_agent,
    router_node,
    summarizer_node,
)
from app.agent.multi.state import MultiAgentState

__all__ = [
    # 状态
    "MultiAgentState",
    # 节点
    "router_node",
    "researcher_node",
    "coder_node",
    "summarizer_node",
    # 路由
    "route_to_agent",
    # 图
    "build_multi_agent_graph",
    "multi_agent_graph",
]
