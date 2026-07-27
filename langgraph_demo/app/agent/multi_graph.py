# -*- coding: utf-8 -*-
"""
多 Agent 协作图

实现多个专业 Agent 的协作系统：
  - 路由器 Agent：分析用户意图，分发任务
  - 研究 Agent：负责信息搜索和知识检索
  - 编码 Agent：负责代码生成和计算
  - 总结 Agent：负责汇总和整理结果

架构图:
    用户输入 → 路由器 → 研究Agent / 编码Agent / 直接回答
                          │              │
                          └──── 总结Agent ←┘
                                  │
                              最终回复
"""

from typing import Literal
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from typing_extensions import TypedDict
from typing import Annotated, List, Optional

from langgraph.graph.message import add_messages

from app.agent.nodes import get_llm
from app.agent.tools import search_knowledge, web_search, calculate
from app.memory import memory_manager
from app.core.logging import get_logger

logger = get_logger(__name__)


# ============================================================
# 多 Agent 状态定义
# ============================================================
class MultiAgentState(TypedDict):
    """多 Agent 协作状态"""
    # 消息列表
    messages: Annotated[List, add_messages]
    # 当前路由目标
    next_agent: Optional[str]
    # 最终结果
    final_result: Optional[str]


# ============================================================
# 路由器节点 - 分析意图并分发
# ============================================================
def router_node(state: MultiAgentState) -> dict:
    """
    路由器节点 - 分析用户意图，决定分发给哪个专业 Agent

    路由规则:
        - 包含搜索/查询类关键词 → researcher
        - 包含计算/代码类关键词 → coder
        - 其他 → summarizer（直接回答）
    """
    logger.info("执行路由器节点")

    messages = state.get("messages", [])
    last_message = messages[-1] if messages else None

    if not last_message:
        return {"next_agent": "summarizer"}

    # 使用 LLM 进行意图分类
    llm = get_llm()
    classification_prompt = [
        SystemMessage(content=(
            "你是一个任务路由器。分析用户的问题，判断应该交给哪个专业 Agent 处理。\n"
            "可选 Agent:\n"
            "- researcher: 负责信息搜索、知识检索、天气查询、网络搜索\n"
            "- coder: 负责数学计算、代码生成、数据分析\n"
            "- summarizer: 负责总结、整理、直接回答简单问题\n\n"
            "只回复 Agent 名称，不要回复其他内容。"
        )),
        last_message,
    ]

    response = llm.invoke(classification_prompt)
    agent_name = response.content.strip().lower()

    # 确保路由到有效 Agent
    valid_agents = ["researcher", "coder", "summarizer"]
    if agent_name not in valid_agents:
        agent_name = "summarizer"

    logger.info(f"路由决策: {agent_name}")
    return {"next_agent": agent_name, "messages": [response]}


# ============================================================
# 路由函数
# ============================================================
def route_to_agent(state: MultiAgentState) -> str:
    """根据路由结果决定下一个节点"""
    next_agent = state.get("next_agent", "summarizer")
    if next_agent == "researcher":
        return "researcher"
    elif next_agent == "coder":
        return "coder"
    else:
        return "summarizer"


# ============================================================
# 研究 Agent - 信息搜索和知识检索
# ============================================================
def researcher_node(state: MultiAgentState) -> dict:
    """
    研究 Agent - 负责信息搜索

    使用工具: search_knowledge, web_search, get_weather
    """
    logger.info("执行研究 Agent")

    messages = state.get("messages", [])
    llm = get_llm()

    # 绑定搜索相关工具
    researcher_tools = [search_knowledge, web_search]
    llm_with_tools = llm.bind_tools(researcher_tools)

    # 添加系统提示
    system_msg = SystemMessage(content=(
        "你是一个研究助手。你的职责是搜索和检索信息。\n"
        "请使用可用工具来获取信息，然后给出详细的研究结果。\n"
        "回答要准确、有条理。"
    ))

    response = llm_with_tools.invoke([system_msg] + messages)
    logger.info(f"研究 Agent 完成")

    return {"messages": [AIMessage(content=response.content, name="researcher")]}


# ============================================================
# 编码 Agent - 计算和代码生成
# ============================================================
def coder_node(state: MultiAgentState) -> dict:
    """
    编码 Agent - 负责计算和代码

    使用工具: calculate
    """
    logger.info("执行编码 Agent")

    messages = state.get("messages", [])
    llm = get_llm()

    # 绑定计算相关工具
    coder_tools = [calculate]
    llm_with_tools = llm.bind_tools(coder_tools)

    # 添加系统提示
    system_msg = SystemMessage(content=(
        "你是一个编码和计算助手。你的职责是解决数学问题和生成代码。\n"
        "请使用计算工具来处理数学表达式。\n"
        "回答要精确、有步骤。"
    ))

    response = llm_with_tools.invoke([system_msg] + messages)
    logger.info(f"编码 Agent 完成")

    return {"messages": [AIMessage(content=response.content, name="coder")]}


# ============================================================
# 总结 Agent - 汇总和整理
# ============================================================
def summarizer_node(state: MultiAgentState) -> dict:
    """
    总结 Agent - 负责汇总结果

    将其他 Agent 的结果整理成最终回复
    """
    logger.info("执行总结 Agent")

    messages = state.get("messages", [])
    llm = get_llm()

    system_msg = SystemMessage(content=(
        "你是一个总结助手。你的职责是整理和汇总信息，给出清晰、简洁的最终回答。\n"
        "如果有其他 Agent 的研究结果，请整合成一份完整的报告。\n"
        "回答要结构清晰、易于理解。"
    ))

    response = llm.invoke([system_msg] + messages)
    logger.info(f"总结 Agent 完成")

    return {
        "messages": [AIMessage(content=response.content, name="summarizer")],
        "final_result": response.content,
    }


# ============================================================
# 构建多 Agent 图
# ============================================================
def build_multi_agent_graph():
    """
    构建多 Agent 协作图

    流程:
        用户输入 → router → researcher / coder / summarizer → END

    Returns:
        CompiledGraph: 编译后的多 Agent 图
    """
    logger.info("构建多 Agent 协作图")

    workflow = StateGraph(MultiAgentState)

    # 添加节点
    workflow.add_node("router", router_node)
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("coder", coder_node)
    workflow.add_node("summarizer", summarizer_node)

    # 设置入口点
    workflow.set_entry_point("router")

    # 路由器条件边
    workflow.add_conditional_edges(
        "router",
        route_to_agent,
        {
            "researcher": "researcher",
            "coder": "coder",
            "summarizer": "summarizer",
        }
    )

    # 所有专业 Agent 执行完后都到 END
    workflow.add_edge("researcher", END)
    workflow.add_edge("coder", END)
    workflow.add_edge("summarizer", END)

    # 编译图
    graph = workflow.compile()
    logger.info("多 Agent 协作图构建完成")

    return graph


# 全局多 Agent 图实例
multi_agent_graph = build_multi_agent_graph()
