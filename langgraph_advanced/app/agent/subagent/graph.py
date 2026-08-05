# -*- coding: utf-8 -*-
"""
Subagent 子图（Supervisor 模式）—— 图构建

本模块负责把 nodes.py 中的节点和路由函数组装成可执行的 LangGraph 子图。

图结构：
                ┌──────────────┐
                │  supervisor  │◄──────────┐
                └──────┬───────┘           │
                       │                   │
       (researcher/coder/analyst)          │
                       │                   │
                       ▼                   │
                ┌──────────────┐           │
                │   worker x   │───────────┘
                └──────────────┘
                       │
                    (FINISH)
                       │
                       ▼
                ┌──────────────┐
                │   finalize   │──► END
                └──────────────┘

学习要点：
    - StateGraph(state_schema) 创建子图，所有节点共享 SubagentState。
    - supervisor 是图的"中心调度器"，worker 全部回到 supervisor 等待再次分发。
    - supervisor 输出 FINISH 时进入 finalize 节点。
    - finalize 节点负责把多次 worker 输出汇总为子图对外可见的 subagent_result。
    - compile() 返回的图可被主图（master_graph）作为节点调用。

企业级要点：
    - 子图实例在模块加载时构建一次（单例），避免每次请求重建。
    - 使用 INFO 级别日志记录关键节点，便于生产环境排障。
"""

from langgraph.graph import END, StateGraph

from app.agent.subagent.nodes import (
    analyst_worker_node,
    coder_worker_node,
    finalize_node,
    researcher_worker_node,
    route_after_supervisor,
    supervisor_node,
)
from app.agent.subagent.state import SubagentState
from app.core.logging import get_logger

logger = get_logger(__name__)


def build_subagent_graph():
    """
    构建 Subagent 子图（Supervisor 模式）

    流程：
        START → supervisor → [researcher / coder / analyst] → supervisor (循环)
                          └─ finalize → END

    Returns:
        CompiledGraph: 编译后的子图，可作为 master_graph 的节点调用。
    """
    logger.info("构建 Subagent 子图（Supervisor 模式）")

    workflow = StateGraph(SubagentState)

    # ------------------------------------------------------------------
    # 注册节点
    # ------------------------------------------------------------------
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("researcher", researcher_worker_node)
    workflow.add_node("coder", coder_worker_node)
    workflow.add_node("analyst", analyst_worker_node)
    workflow.add_node("finalize", finalize_node)

    # ------------------------------------------------------------------
    # 入口：supervisor
    # ------------------------------------------------------------------
    workflow.set_entry_point("supervisor")

    # ------------------------------------------------------------------
    # supervisor → worker / finalize（条件路由）
    # ------------------------------------------------------------------
    workflow.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {
            "researcher": "researcher",
            "coder": "coder",
            "analyst": "analyst",
            "finalize": "finalize",
        },
    )

    # ------------------------------------------------------------------
    # worker → supervisor（循环分发，直到 supervisor 输出 FINISH）
    # ------------------------------------------------------------------
    workflow.add_edge("researcher", "supervisor")
    workflow.add_edge("coder", "supervisor")
    workflow.add_edge("analyst", "supervisor")

    # ------------------------------------------------------------------
    # finalize → END
    # ------------------------------------------------------------------
    workflow.add_edge("finalize", END)

    # ------------------------------------------------------------------
    # 编译
    # ------------------------------------------------------------------
    graph = workflow.compile()
    logger.info("Subagent 子图构建完成")
    return graph


# 全局 Subagent 子图实例（单例）
# 说明：在模块加载时构建一次；master_graph 通过该实例把整个子图作为节点调用。
subagent_graph = build_subagent_graph()
