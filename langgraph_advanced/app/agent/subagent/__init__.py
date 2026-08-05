# -*- coding: utf-8 -*-
"""
Subagent 子图（Supervisor 模式）

对外统一从本包导入：
    from app.agent.subagent import build_subagent_graph, subagent_graph

包内职责：
    - state.py : 状态定义（SubagentState）
    - nodes.py : 节点与路由函数（supervisor / researcher / coder / analyst / finalize）
    - graph.py : 图构建与全局实例

与 master_graph 的关系：
    master_graph 的 subagent_node 把本子图作为节点调用，
    通过入口/出口映射与 MasterState 隔离。
"""

from app.agent.subagent.graph import build_subagent_graph, subagent_graph
from app.agent.subagent.nodes import (
    AVAILABLE_WORKERS,
    SupervisorDecision,
    analyst_worker_node,
    coder_worker_node,
    finalize_node,
    researcher_worker_node,
    route_after_supervisor,
    supervisor_node,
)
from app.agent.subagent.state import SubagentState

__all__ = [
    # 状态
    "SubagentState",
    # 结构化输出
    "SupervisorDecision",
    "AVAILABLE_WORKERS",
    # 节点
    "supervisor_node",
    "researcher_worker_node",
    "coder_worker_node",
    "analyst_worker_node",
    "finalize_node",
    # 路由
    "route_after_supervisor",
    # 图
    "build_subagent_graph",
    "subagent_graph",
]
