# -*- coding: utf-8 -*-
"""
并行执行（Fan-out/Fan-in）实现

并行执行是 LangGraph 的高级特性之一。
它允许同时执行多个任务，然后聚合结果。

学习要点：
1. Fan-out: 一个节点分发多个任务
2. Fan-in: 多个节点聚合结果
3. 使用 Send API 实现动态并行
4. 并行任务可以显著提高性能

使用场景：
- 并行搜索多个数据源
- 并行处理多个文件
- 并行调用多个 API
- 并行执行多个分析任务

架构图：
    distributor → [worker1, worker2, worker3] → aggregator
         ↓              ↓           ↓           ↓
    分发任务        处理任务1    处理任务2    处理任务3
         ↓              ↓           ↓           ↓
         └──────────────┴───────────┴───────────┘
                          ↓
                    聚合所有结果
"""

import asyncio
from typing import Annotated, List, Optional
from typing_extensions import TypedDict

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.constants import Send

from app.agent.nodes import get_llm
from app.agent.tools import web_search, search_knowledge
from app.core.logging import get_logger

logger = get_logger(__name__)


# ============================================================
# 并行执行状态定义
# ============================================================
class ParallelState(TypedDict):
    """
    并行执行状态
    
    包含：
    - messages: 对话消息
    - tasks: 任务列表（分发给多个 worker）
    - worker_results: Worker 结果列表
    - final_result: 聚合后的最终结果
    """
    # 消息列表
    messages: Annotated[List[BaseMessage], add_messages]
    
    # 任务列表（每个任务是一个查询字符串）
    tasks: List[str]
    
    # Worker 结果列表（每个 worker 的处理结果）
    worker_results: List[str]
    
    # 聚合后的最终结果
    final_result: Optional[str]


# ============================================================
# 节点1: 分发节点（Fan-out）
# ============================================================
def distributor_node(state: ParallelState) -> dict:
    """
    分发节点 - 将任务分发给多个 worker
    
    这个节点负责：
    1. 从状态中获取任务列表
    2. 为每个任务创建一个 Send 对象
    3. 返回 Send 列表，触发并行执行
    
    Args:
        state: 并行执行状态
    
    Returns:
        dict: 包含 Send 列表的状态更新
    
    学习要点：
    - Send API 允许动态创建并行任务
    - 每个 Send 对象指定目标节点和输入状态
    - LangGraph 会自动并行执行所有 Send
    """
    logger.info("执行分发节点")
    
    messages = state.get("messages", [])
    query = messages[-1].content if messages else ""
    
    # 根据查询生成多个子任务
    # 实际场景可以根据业务逻辑动态生成
    tasks = [
        f"搜索知识库: {query}",
        f"网络搜索: {query}",
        f"分析总结: {query}",
    ]
    
    logger.info(f"分发 {len(tasks)} 个任务")
    
    return {
        "tasks": tasks,
        "worker_results": [],
    }


# ============================================================
# 节点2: Worker 节点（并行执行）
# ============================================================
def worker_node(state: dict) -> dict:
    """
    Worker 节点 - 处理单个任务
    
    这个节点会被并行调用多次，每次处理一个任务。
    
    Args:
        state: 单个任务的状态（包含 task 字段）
    
    Returns:
        dict: 任务结果
    
    学习要点：
    - Worker 节点接收单个任务的状态
    - 多个 worker 可以并行执行
    - 每个 worker 返回的结果会被收集
    """
    task = state.get("task", "")
    logger.info(f"Worker 执行任务: {task}")
    
    # 根据任务类型执行不同的操作
    if "知识库" in task:
        # 知识库搜索
        result = search_knowledge.invoke({"query": task, "max_results": 3})
    elif "网络搜索" in task:
        # 网络搜索
        result = web_search.invoke({"query": task, "max_results": 3})
    else:
        # 使用 LLM 分析
        llm = get_llm()
        response = llm.invoke([
            SystemMessage(content="请分析并总结以下内容："),
            AIMessage(content=task),
        ])
        result = response.content
    
    logger.info(f"Worker 完成任务: {task[:50]}...")
    
    return {
        "result": result,
    }


# ============================================================
# 节点3: 聚合节点（Fan-in）
# ============================================================
def aggregator_node(state: ParallelState) -> dict:
    """
    聚合节点 - 汇总所有 worker 的结果
    
    这个节点负责：
    1. 从状态中收集所有 worker 的结果
    2. 使用 LLM 整合结果
    3. 生成最终的综合报告
    
    Args:
        state: 并行执行状态
    
    Returns:
        dict: 状态更新（包含最终结果）
    
    学习要点：
    - 聚合节点在所有 worker 完成后执行
    - 可以使用 LLM 整合多个结果
    - 生成最终的综合报告
    """
    logger.info("执行聚合节点")
    
    worker_results = state.get("worker_results", [])
    
    if not worker_results:
        logger.warning("没有 worker 结果可聚合")
        return {
            "final_result": "未获取到任何结果",
            "messages": [AIMessage(content="未获取到任何结果")],
        }
    
    # 使用 LLM 整合所有结果
    llm = get_llm()
    
    aggregation_prompt = [
        SystemMessage(content=(
            "你是一个信息整合专家。根据提供的多个搜索结果，生成一份综合报告。\n"
            "要求：\n"
            "1. 提取所有结果中的关键信息\n"
            "2. 去除重复内容\n"
            "3. 按重要性排序\n"
            "4. 生成结构清晰的综合报告"
        )),
        AIMessage(content=f"以下是 {len(worker_results)} 个搜索结果：\n\n" + 
                  "\n\n---\n\n".join(worker_results)),
    ]
    
    response = llm.invoke(aggregation_prompt)
    final_result = response.content
    
    logger.info("聚合完成")
    
    return {
        "final_result": final_result,
        "messages": [AIMessage(content=final_result)],
    }


# ============================================================
# 路由函数：动态创建并行任务
# ============================================================
def route_to_workers(state: ParallelState) -> list:
    """
    路由到 worker 节点 - 动态创建并行任务
    
    这个函数返回 Send 列表，每个 Send 对象会触发一个 worker 执行。
    
    Args:
        state: 并行执行状态
    
    Returns:
        list: Send 对象列表
    
    学习要点：
    - Send API 是 LangGraph 实现 Fan-out 的关键
    - 每个 Send 指定目标节点和输入状态
    - LangGraph 会自动并行执行所有 Send
    - 所有 worker 完成后，会进入下一个节点
    """
    tasks = state.get("tasks", [])
    
    if not tasks:
        logger.warning("没有任务可分发")
        return []
    
    # 为每个任务创建一个 Send 对象
    sends = [
        Send("worker", {"task": task})
        for task in tasks
    ]
    
    logger.info(f"创建 {len(sends)} 个并行任务")
    return sends


# ============================================================
# 构建并行执行图
# ============================================================
def build_parallel_graph():
    """
    构建并行执行图
    
    流程：
        START → distributor → [worker1, worker2, worker3] → aggregator → END
    
    学习要点：
    - 使用 Send API 实现动态并行
    - 所有 worker 并行执行
    - 聚合节点等待所有 worker 完成
    - 这种模式可以显著提高性能
    
    Returns:
        CompiledGraph: 编译后的并行执行图
    """
    logger.info("构建并行执行图")
    
    # 创建状态图
    workflow = StateGraph(ParallelState)
    
    # 添加节点
    workflow.add_node("distributor", distributor_node)
    workflow.add_node("worker", worker_node)
    workflow.add_node("aggregator", aggregator_node)
    
    # 设置入口点
    workflow.set_entry_point("distributor")
    
    # distributor → workers（使用 Send API 动态创建并行任务）
    workflow.add_conditional_edges(
        "distributor",
        route_to_workers,
        ["worker"]  # 目标节点列表
    )
    
    # workers → aggregator（所有 worker 完成后进入聚合节点）
    workflow.add_edge("worker", "aggregator")
    
    # aggregator → END
    workflow.add_edge("aggregator", END)
    
    # 编译图
    graph = workflow.compile()
    
    logger.info("并行执行图构建完成")
    return graph


# 全局图实例
parallel_graph = build_parallel_graph()


# ============================================================
# 使用示例
# ============================================================
"""
使用示例：

# 1. 准备初始状态
initial_state = {
    "messages": [HumanMessage(content="LangGraph 教程")],
    "tasks": [],
    "worker_results": [],
    "final_result": None,
}

# 2. 执行并行图
result = parallel_graph.invoke(initial_state)

# 3. 获取最终结果
print(result["final_result"])
"""
