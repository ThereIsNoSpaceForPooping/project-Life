# -*- coding: utf-8 -*-
"""
子图（Subgraph）实现

子图是 LangGraph 的高级特性之一，允许将一个图嵌套在另一个图中。

学习要点：
1. 子图可以有独立的状态结构
2. 子图可以作为主图的一个节点
3. 子图的状态会自动映射到主图状态
4. 子图实现功能复用和模块化

使用场景：
- 研究-写作流程：研究子图 + 写作节点
- 复杂任务分解：将大任务拆分为多个子图
- 功能复用：同一个子图可以在多个主图中使用

架构图：
    主图: START → research(子图) → write → END
              │
              └─ 子图: search → analyze → compile
"""

from typing import Annotated, List, Optional
from typing_extensions import TypedDict

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from app.agent.nodes import get_llm
from app.agent.tools import search_knowledge, web_search
from app.core.logging import get_logger

logger = get_logger(__name__)


# ============================================================
# 子图状态定义
# ============================================================
class ResearchSubgraphState(TypedDict):
    """
    研究子图状态
    
    子图可以有独立的状态结构，与主图解耦。
    主图可以通过状态映射获取子图的结果。
    """
    # 消息列表
    messages: Annotated[List[BaseMessage], add_messages]
    
    # 研究查询（输入）
    query: str
    
    # 搜索结果（中间数据）
    search_results: List[str]
    
    # 分析结果（中间数据）
    analysis: Optional[str]
    
    # 最终研究报告（输出）
    report: Optional[str]


# ============================================================
# 子图节点1: 搜索节点
# ============================================================
def search_node(state: ResearchSubgraphState) -> dict:
    """
    搜索节点 - 执行信息搜索
    
    这是子图的第一个节点，负责：
    1. 从状态中获取查询
    2. 调用搜索工具
    3. 将结果存储到状态中
    
    Args:
        state: 子图状态
    
    Returns:
        dict: 状态更新
    """
    logger.info("子图: 执行搜索节点")
    
    query = state.get("query", "")
    
    # 调用知识库搜索
    knowledge_results = search_knowledge.invoke({"query": query, "max_results": 3})
    
    # 调用网络搜索
    web_results = web_search.invoke({"query": query, "max_results": 3})
    
    # 合并搜索结果
    all_results = [knowledge_results, web_results]
    
    logger.info(f"子图: 搜索完成，获取到 {len(all_results)} 组结果")
    
    return {
        "search_results": all_results,
        "messages": [AIMessage(content=f"搜索完成，找到 {len(all_results)} 组结果")],
    }


# ============================================================
# 子图节点2: 分析节点
# ============================================================
def analyze_node(state: ResearchSubgraphState) -> dict:
    """
    分析节点 - 分析搜索结果
    
    这是子图的第二个节点，负责：
    1. 从状态中获取搜索结果
    2. 使用 LLM 分析结果
    3. 提取关键信息
    
    Args:
        state: 子图状态
    
    Returns:
        dict: 状态更新
    """
    logger.info("子图: 执行分析节点")
    
    search_results = state.get("search_results", [])
    query = state.get("query", "")
    
    # 使用 LLM 分析搜索结果
    llm = get_llm()
    
    analysis_prompt = [
        SystemMessage(content=(
            "你是一个研究分析师。根据提供的搜索结果，提取关键信息并进行分析。\n"
            "要求：\n"
            "1. 提取与查询最相关的信息\n"
            "2. 识别关键观点和事实\n"
            "3. 总结主要发现\n"
            "4. 指出信息的可靠性"
        )),
        AIMessage(content=f"查询: {query}\n\n搜索结果:\n{chr(10).join(search_results)}"),
    ]
    
    response = llm.invoke(analysis_prompt)
    analysis = response.content
    
    logger.info("子图: 分析完成")
    
    return {
        "analysis": analysis,
        "messages": [AIMessage(content="分析完成")],
    }


# ============================================================
# 子图节点3: 编译报告节点
# ============================================================
def compile_report_node(state: ResearchSubgraphState) -> dict:
    """
    编译报告节点 - 生成最终研究报告
    
    这是子图的最后一个节点，负责：
    1. 从状态中获取分析结果
    2. 使用 LLM 生成结构化报告
    3. 将报告存储到状态中
    
    Args:
        state: 子图状态
    
    Returns:
        dict: 状态更新
    """
    logger.info("子图: 执行编译报告节点")
    
    analysis = state.get("analysis", "")
    query = state.get("query", "")
    
    # 使用 LLM 生成报告
    llm = get_llm()
    
    report_prompt = [
        SystemMessage(content=(
            "你是一个研究报告撰写专家。根据分析结果，撰写一份结构清晰的研究报告。\n"
            "报告结构：\n"
            "1. 摘要\n"
            "2. 主要发现\n"
            "3. 详细分析\n"
            "4. 结论\n"
            "5. 参考来源"
        )),
        AIMessage(content=f"查询: {query}\n\n分析结果:\n{analysis}"),
    ]
    
    response = llm.invoke(report_prompt)
    report = response.content
    
    logger.info("子图: 报告编译完成")
    
    return {
        "report": report,
        "messages": [AIMessage(content=report)],
    }


# ============================================================
# 构建研究子图
# ============================================================
def build_research_subgraph():
    """
    构建研究子图
    
    子图流程:
        START → search → analyze → compile_report → END
    
    Returns:
        CompiledGraph: 编译后的子图
    
    学习要点：
    - 子图的构建方式与主图完全相同
    - 子图有自己的状态结构和节点
    - 子图编译后可以直接作为主图的节点使用
    """
    logger.info("构建研究子图")
    
    # 创建状态图
    workflow = StateGraph(ResearchSubgraphState)
    
    # 添加节点
    workflow.add_node("search", search_node)
    workflow.add_node("analyze", analyze_node)
    workflow.add_node("compile_report", compile_report_node)
    
    # 设置入口点
    workflow.set_entry_point("search")
    
    # 添加边（线性流程）
    workflow.add_edge("search", "analyze")
    workflow.add_edge("analyze", "compile_report")
    workflow.add_edge("compile_report", END)
    
    # 编译子图（不需要 checkpointer，子图通常是短生命周期的）
    subgraph = workflow.compile()
    
    logger.info("研究子图构建完成")
    return subgraph


# ============================================================
# 主图节点：调用子图
# ============================================================
def research_node(state: dict) -> dict:
    """
    研究节点 - 在主图中调用研究子图
    
    这个节点展示了如何在主图中使用子图：
    1. 从主图状态中提取输入
    2. 构造子图初始状态
    3. 调用子图
    4. 从子图结果中提取输出
    
    Args:
        state: 主图状态
    
    Returns:
        dict: 状态更新
    """
    logger.info("主图: 执行研究节点（调用子图）")
    
    # 获取查询
    messages = state.get("messages", [])
    query = messages[-1].content if messages else ""
    
    # 构建子图
    research_subgraph = build_research_subgraph()
    
    # 构造子图初始状态
    subgraph_input = {
        "query": query,
        "messages": [],
        "search_results": [],
        "analysis": None,
        "report": None,
    }
    
    # 调用子图
    subgraph_result = research_subgraph.invoke(subgraph_input)
    
    # 从子图结果中提取报告
    report = subgraph_result.get("report", "研究完成，但未生成报告")
    
    logger.info("主图: 研究节点完成")
    
    return {
        "messages": [AIMessage(content=report)],
        "final_result": report,
    }


# ============================================================
# 构建包含子图的主图
# ============================================================
def build_main_graph_with_subgraph():
    """
    构建包含子图的主图
    
    主图流程:
        START → research(子图) → write → END
    
    学习要点：
    - 子图可以作为主图的一个节点
    - 主图可以组合多个子图
    - 这种模式实现了功能复用和模块化
    
    Returns:
        CompiledGraph: 编译后的主图
    """
    from app.agent.state import AgentState
    
    logger.info("构建包含子图的主图")
    
    # 创建主图
    workflow = StateGraph(AgentState)
    
    # 添加节点（子图作为节点）
    workflow.add_node("research", research_node)
    
    # 设置入口点
    workflow.set_entry_point("research")
    
    # 研究完成后直接结束
    workflow.add_edge("research", END)
    
    # 编译主图
    graph = workflow.compile()
    
    logger.info("包含子图的主图构建完成")
    return graph


# 全局图实例
research_graph = build_main_graph_with_subgraph()
