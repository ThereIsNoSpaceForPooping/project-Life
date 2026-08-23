# -*- coding: utf-8 -*-
"""
Agent 模块聚合导出层（Facade）

本文件是整个 ``app.agent`` 包的"对外门面"。
对调用方隐藏内部按"图（graph）/节点（nodes）/状态（state）"切分的目录结构，
对外保持向后兼容的"扁平"导入风格。

设计目标：
    1. **向后兼容**：旧的 ``from app.agent import agent_graph, master_graph, ...``
       写法继续可用，无需修改调用方。
    2. **结构清晰**：内部按图维度拆分为 ``single / master / multi / subagent``，
       每个图都有独立的 ``state.py / nodes.py / graph.py``。
    3. **统一共享**：LLM 工厂、工具管理器、本地工具、Map-Reduce 工具
       全部下沉到 ``app.agent.shared`` 子包，避免重复实现。
    4. **新代码推荐**：新代码应直接 ``from app.agent.single import ...`` /
       ``from app.agent.shared import ...``，走更精确的子模块路径。

包内子模块清单：
    - app.agent.single     : 单 Agent（ReAct + 人机协作）
    - app.agent.master     : 统一大图（集成所有高级功能）
    - app.agent.multi      : 多 Agent 协作（Supervisor-Worker 简化版）
    - app.agent.subagent   : Subagent 子图（Supervisor-Worker 完整版）
    - app.agent.shared     : 共享基础设施（LLM / Tool / Map-Reduce）
    - app.agent.advanced   : 高级特性独立图（Map-Reduce / Parallel / Time-Travel ...）
    - app.agent.a2a        : A2A 协议相关
    - app.agent.mcp        : MCP 工具协议相关
    - app.agent.middleware : 中间件（prebuilt 工具节点 / 死循环守卫）
"""

# ============================================================
# 共享基础设施（LLM / 工具 / Map-Reduce 工具函数）
# 用途：所有图都可能复用
# ============================================================
from app.agent.shared.llm import get_llm
from app.agent.shared.tool_manager import ToolManager, tool_manager
from app.agent.shared.tools import (
    TOOLS,
    TOOL_CATEGORIES,
    calculate,
    get_current_time,
    get_tools_by_category,
    get_tools_by_names,
    get_weather,
    search_knowledge,
    web_search,
)
from app.agent.shared.mapreduce_utils import (
    MAX_CHUNK_CHARS,
    map_summarize_chunk,
    split_text,
)

# ============================================================
# 单 Agent（ReAct 模式，可选人机协作）
# 旧路径：app.agent.state.AgentState / app.agent.nodes.* / app.agent.graph.*
# ============================================================
from app.agent.single.state import AgentState
from app.agent.single.nodes import (
    agent_node,
    human_review_node,
    should_continue,
    should_review,
    tool_node,
)
from app.agent.single.graph import agent_graph, build_agent_graph

# ============================================================
# 多 Agent 协作（multi graph）
# 旧路径：app.agent.multi_graph.*
# ============================================================
from app.agent.multi.state import MultiAgentState
from app.agent.multi.nodes import (
    coder_node,
    researcher_node,
    route_to_agent,
    router_node,
    summarizer_node,
)
from app.agent.multi.graph import build_multi_agent_graph, multi_agent_graph

# ============================================================
# 统一大图（master graph）
# 旧路径：app.agent.master_graph.*
# ============================================================
from app.agent.master.state import MasterState, ReflectionResult, TaskAnalysis
from app.agent.master.graph import build_master_graph, master_graph

# ============================================================
# Subagent 子图（Supervisor-Worker 模式）
# 旧路径：app.agent.subagent_graph.*
# ============================================================
from app.agent.subagent.state import SubagentState
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
from app.agent.subagent.graph import build_subagent_graph, subagent_graph


# ============================================================
# 显式 __all__ —— 既是文档，也控制 ``from app.agent import *`` 的范围
# ============================================================
__all__ = [
    # ---- 共享基础设施 ----
    "get_llm",
    "ToolManager",
    "tool_manager",
    "TOOLS",
    "TOOL_CATEGORIES",
    "get_tools_by_category",
    "get_tools_by_names",
    "get_weather",
    "calculate",
    "search_knowledge",
    "web_search",
    "get_current_time",
    "MAX_CHUNK_CHARS",
    "split_text",
    "map_summarize_chunk",
    # ---- 单 Agent ----
    "AgentState",
    "agent_node",
    "tool_node",
    "human_review_node",
    "should_continue",
    "should_review",
    "agent_graph",
    "build_agent_graph",
    # ---- 多 Agent ----
    "MultiAgentState",
    "router_node",
    "researcher_node",
    "coder_node",
    "summarizer_node",
    "route_to_agent",
    "multi_agent_graph",
    "build_multi_agent_graph",
    # ---- 统一大图 ----
    "MasterState",
    "TaskAnalysis",
    "ReflectionResult",
    "master_graph",
    "build_master_graph",
    # ---- Subagent 子图 ----
    "SubagentState",
    "SupervisorDecision",
    "AVAILABLE_WORKERS",
    "supervisor_node",
    "researcher_worker_node",
    "coder_worker_node",
    "analyst_worker_node",
    "finalize_node",
    "route_after_supervisor",
    "subagent_graph",
    "build_subagent_graph",
]
