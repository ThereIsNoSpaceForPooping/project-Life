# -*- coding: utf-8 -*-
"""
多 Agent 协作图 —— 图构建

本模块负责把 nodes.py 中的节点和路由函数组装成可执行的 LangGraph 图。

图结构：
    START
      │
      ▼
    router  ──(researcher)──► researcher ──► END
      │ ──(coder)─────────► coder       ──► END
      └─(summarizer)──────► summarizer  ──► END

学习要点：
    - StateGraph(state_schema) 创建图，所有节点共享同一份状态。
    - add_node(name, fn) 注册节点；同名可重复注册（覆盖）。
    - set_entry_point(name) 指定图入口。
    - add_conditional_edges(src, path, path_map) 根据 path 函数的返回值路由。
    - add_edge(src, dst) 固定边，无条件跳转。
    - compile() 返回 CompiledGraph 实例，可直接 invoke / stream。

企业级要点：
    - 图实例在模块加载时构建一次（全局单例），避免每次请求重新构建。
    - 使用 INFO 级别日志记录关键节点，便于生产环境排障。
"""

from langgraph.graph import END, StateGraph

from app.agent.multi.nodes import (
    coder_node,
    researcher_node,
    route_to_agent,
    router_node,
    summarizer_node,
)
from app.agent.multi.state import MultiAgentState
from app.core.logging import get_logger

logger = get_logger(__name__)


def build_multi_agent_graph():
    """
    构建多 Agent 协作图

    流程:
        用户输入 → router → researcher / coder / summarizer → END

    Returns:
        CompiledGraph: 编译后的多 Agent 图

    学习要点：
        - 条件边返回 "researcher" / "coder" / "summarizer"，
          与下方 path_map 的 keys 一一对应。
        - 专业 Agent 节点执行完后统一跳到 END，不强制汇聚到 summarizer；
          summarizer 仅作为"无明确分工具意图"时的兜底收口节点。
    """
    logger.info("构建多 Agent 协作图")

    # 创建状态图（所有节点共享 MultiAgentState）
    workflow = StateGraph(MultiAgentState)

    # ------------------------------------------------------------------
    # 注册节点
    # ------------------------------------------------------------------
    workflow.add_node("router", router_node)
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("coder", coder_node)
    workflow.add_node("summarizer", summarizer_node)

    # ------------------------------------------------------------------
    # 设置入口
    # ------------------------------------------------------------------
    workflow.set_entry_point("router")

    # ------------------------------------------------------------------
    # 路由器条件边：根据 route_to_agent 的返回值分发
    # ------------------------------------------------------------------
    workflow.add_conditional_edges(
        "router",
        route_to_agent,
        {
            "researcher": "researcher",
            "coder": "coder",
            "summarizer": "summarizer",
        },
    )

    # ------------------------------------------------------------------
    # 专业 Agent 执行完统一跳到 END
    # ------------------------------------------------------------------
    workflow.add_edge("researcher", END)
    workflow.add_edge("coder", END)
    workflow.add_edge("summarizer", END)

    # ------------------------------------------------------------------
    # 编译为可执行图
    # ------------------------------------------------------------------
    graph = workflow.compile()
    logger.info("多 Agent 协作图构建完成")
    return graph


# 全局多 Agent 图实例（单例）
# 说明：在模块加载时构建一次；后续请求复用同一份图，避免每次重建开销。
multi_agent_graph = build_multi_agent_graph()
