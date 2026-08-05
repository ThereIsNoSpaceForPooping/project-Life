# -*- coding: utf-8 -*-
"""
统一大图（Master Graph）—— 图构建

本模块负责把 nodes.py 中的节点、路由函数组装成可执行的 LangGraph 图。

图结构（v2 —— 防死循环重构）：
    START
      │
      ▼
    guard_input ──(不安全)──► summarizer ──► END
      │
      │(安全)
      ▼
    router ──► research_subgraph ──┐
      │                              │
      │       mapreduce ─────────────┤
      │                              │
      │       subagent ──────────────┼──► agent
      │                              │       │
      │                              │       │(有 tool_calls)
      │                              │       ▼
      │                              │   stuck_guard ──► human_review
      │                              │       │              │
      │                              │       │(强制跳过)    │(批准 + 未超限)
      │                              │       │              ▼
      │                              │       │            tools
      │                              │       │              │
      │                              │       │              ▼
      │                              │       │            agent (循环)
      │                              │       │
      │                              │       └─► reflection ──► guard_output
      │                              │                        ──► summarizer
      │                              │                            ──► END

三层防死循环：
    1. stuck_guard       : 连续 N 次相同 (tool, args) 立即拦截
    2. max_tool_calls    : 累计硬上限（默认 5）
    3. recursion_limit   : chat.py 调用处兜底（默认 15）

学习要点：
    - 所有功能集成在一个图中
    - 通过条件路由实现分支
    - 防循环责任分层：业务层（stuck_guard）+ 资源层（max_tool_calls）+ 框架层（recursion_limit）
    - 带 checkpointer 支持时间旅行

企业级要点：
    - 图实例在模块加载时构建一次（全局单例），避免每次请求重新构建。
    - 使用 INFO 级别日志记录关键节点，便于生产环境排障。
"""

from langgraph.graph import END, StateGraph

from app.agent.master.nodes import (
    _build_prebuilt_tool_node,
    _stuck_guard_node_wrapper,
    agent_node,
    auto_explore_node,
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
from app.agent.master.state import MasterState
from app.core.logging import get_logger
from app.memory import memory_manager

logger = get_logger(__name__)


def build_master_graph():
    """
    构建统一大图（v2 —— 防死循环重构）

    Returns:
        CompiledGraph: 编译后的 LangGraph 图实例

    学习要点：
        - set_entry_point() 设置入口节点。
        - add_conditional_edges(src, path, path_map) 根据 path 函数的返回值路由。
        - add_edge(src, dst) 固定边，无条件跳转。
        - compile(checkpointer=...) 编译图并挂载 checkpointer，支持时间旅行。
    """
    logger.info("构建统一大图（v2 防死循环重构）")

    # ------------------------------------------------------------------
    # 创建状态图（所有节点共享 MasterState）
    # ------------------------------------------------------------------
    workflow = StateGraph(MasterState)

    # ------------------------------------------------------------------
    # 注册节点
    # ------------------------------------------------------------------
    workflow.add_node("guard_input", guard_input_node)
    workflow.add_node("router", router_node)
    workflow.add_node("research_subgraph", research_subgraph_node)
    workflow.add_node("mapreduce", mapreduce_node)
    workflow.add_node("subagent", subagent_node)
    workflow.add_node("agent", agent_node)

    # v2 新增：stuck_guard 守卫节点
    workflow.add_node("stuck_guard", _stuck_guard_node_wrapper)

    # v2 重构：使用 PrebuiltToolNode 替代手写 tool_node_master
    prebuilt_tools = _build_prebuilt_tool_node()
    workflow.add_node("tools", prebuilt_tools)

    workflow.add_node("human_review", human_review_node)
    workflow.add_node("reflection", reflection_node)
    workflow.add_node("guard_output", guard_output_node)
    workflow.add_node("summarizer", summarizer_node)
    workflow.add_node("auto_explore", auto_explore_node)

    # ------------------------------------------------------------------
    # 边：入口与分叉
    # ------------------------------------------------------------------
    workflow.set_entry_point("guard_input")

    workflow.add_conditional_edges(
        "guard_input",
        route_after_guard_input,
        {
            "router": "router",
            "summarizer": "summarizer",
        },
    )

    workflow.add_conditional_edges(
        "router",
        route_after_router,
        {
            "research_subgraph": "research_subgraph",
            "mapreduce": "mapreduce",
            "subagent": "subagent",
            "agent": "agent",
        },
    )

    # 所有处理路径最终汇聚到 agent
    workflow.add_edge("research_subgraph", "agent")
    workflow.add_edge("mapreduce", "agent")
    workflow.add_edge("subagent", "agent")

    # ------------------------------------------------------------------
    # 边：核心循环（v2 —— 含 stuck_guard）
    # ------------------------------------------------------------------
    workflow.add_conditional_edges(
        "agent",
        route_after_agent,
        {
            "stuck_guard": "stuck_guard",
            "reflection": "reflection",
        },
    )

    workflow.add_conditional_edges(
        "stuck_guard",
        route_after_stuck_guard_wrapper,
        {
            "human_review": "human_review",
            "reflection": "reflection",
        },
    )

    workflow.add_conditional_edges(
        "human_review",
        route_after_human_review,
        {
            "tools": "tools",
            "reflection": "reflection",
        },
    )

    # tools → agent（工具执行后回到 Agent 生成最终回答）
    workflow.add_edge("tools", "agent")

    # ------------------------------------------------------------------
    # 边：尾部（反思 → 输出过滤 → 汇总）
    # ------------------------------------------------------------------
    workflow.add_conditional_edges(
        "reflection",
        route_after_reflection,
        {
            "guard_output": "guard_output",
            "agent": "agent",
        },
    )

    workflow.add_edge("guard_output", "summarizer")
    workflow.add_edge("summarizer", END)

    # ------------------------------------------------------------------
    # 编译（带 checkpointer 支持时间旅行）
    # ------------------------------------------------------------------
    graph = workflow.compile(checkpointer=memory_manager.checkpointer)

    logger.info("统一大图构建完成（v2）")
    return graph


# 全局图实例（单例）
# 说明：在模块加载时构建一次；后续请求复用同一份图，避免每次重建开销。
master_graph = build_master_graph()
