# -*- coding: utf-8 -*-
"""
多 Agent 协作图 —— 节点定义

本模块定义多 Agent 协作图的所有节点与路由函数：

节点清单：
    - router_node     : 意图路由器（LLM 分类 → next_agent）
    - researcher_node : 信息检索专家（绑定 search_knowledge / web_search）
    - coder_node      : 编码与计算专家（绑定 calculate）
    - summarizer_node : 汇总节点（不绑定工具，输出最终结果并写入 final_result）

路由函数：
    - route_to_agent  : 读取 next_agent 字段，返回下一跳节点名

学习要点：
    - 路由器使用 LLM 进行意图分类（结构化文本输出）。
    - 每个专业 Agent 拥有独立的工具集合，体现"分工"思想。
    - 条件边根据 route_to_agent 的返回值动态分发。
"""

from typing import List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agent.multi.state import MultiAgentState
from app.agent.shared.llm import get_llm
from app.agent.shared.tools import calculate, search_knowledge, web_search
from app.core.logging import get_logger

logger = get_logger(__name__)


# ============================================================
# 路由器节点 - 分析意图并分发
# ============================================================
def router_node(state: MultiAgentState) -> dict:
    """
    路由器节点 - 分析用户意图，决定分发给哪个专业 Agent

    路由规则（LLM 分类）：
        - 包含搜索/查询类关键词 → researcher
        - 包含计算/代码类关键词 → coder
        - 其他 → summarizer（直接回答）

    Returns:
        dict: 状态更新字段
            - next_agent: 目标 Agent 名称
            - messages  : 追加一条 AIMessage（路由器自身的决策回复）

    学习要点：
        - 使用 LLM 进行智能路由；prompt 中明确列出可选 Agent。
        - 校验 LLM 返回值，避免幻觉导致的非法路由名。
        - 把路由决策作为 AIMessage 追加到 messages，便于审计/可观测。
    """
    logger.info("执行路由器节点")

    messages = state.get("messages", [])
    last_message = messages[-1] if messages else None

    # 防御：空消息时直接走 summarizer，避免 LLM 幻觉
    if not last_message:
        logger.warning("路由器未拿到任何消息，默认路由到 summarizer")
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
    agent_name = (response.content or "").strip().lower()

    # 校验 LLM 输出：未命中已知 Agent 时回退到 summarizer，保证图不会卡死
    valid_agents = ["researcher", "coder", "summarizer"]
    if agent_name not in valid_agents:
        logger.warning(f"路由器返回未知 Agent: {agent_name}，回退到 summarizer")
        agent_name = "summarizer"

    logger.info(f"路由决策: {agent_name}")
    return {"next_agent": agent_name, "messages": [response]}


# ============================================================
# 路由函数
# ============================================================
def route_to_agent(state: MultiAgentState) -> str:
    """
    条件边路由函数 - 读取 next_agent 并返回下一跳节点名

    Args:
        state: 多 Agent 状态（TypedDict）

    Returns:
        str: 下一个节点名称（researcher / coder / summarizer）

    学习要点：
        - 该函数是 add_conditional_edges 的第一个参数（path map 函数）。
        - 返回值必须与 add_conditional_edges 的 path_map 字典 keys 对应。
        - 任何分支都必须有显式 return，禁止依赖默认 None。
    """
    next_agent = state.get("next_agent", "summarizer")
    if next_agent == "researcher":
        return "researcher"
    if next_agent == "coder":
        return "coder"
    return "summarizer"


# ============================================================
# 研究 Agent - 信息搜索和知识检索
# ============================================================
def researcher_node(state: MultiAgentState) -> dict:
    """
    研究 Agent - 负责信息搜索与知识检索

    工具集合：search_knowledge, web_search

    Returns:
        dict: 状态更新字段（追加一条来自 researcher 的 AIMessage）

    学习要点：
        - 不同 Agent 绑定不同工具集，体现"专业分工"。
        - SystemMessage 明确 Agent 角色，让 LLM 行为稳定。
    """
    logger.info("执行研究 Agent")

    messages = state.get("messages", [])
    llm = get_llm()

    # 绑定研究类工具
    researcher_tools = [search_knowledge, web_search]
    llm_with_tools = llm.bind_tools(researcher_tools)

    # 角色说明：约束 LLM 输出风格
    system_msg = SystemMessage(content=(
        "你是一个研究助手。你的职责是搜索和检索信息。\n"
        "请使用可用工具来获取信息，然后给出详细的研究结果。\n"
        "回答要准确、有条理。"
    ))

    response = llm_with_tools.invoke([system_msg] + messages)
    logger.info("研究 Agent 完成")

    return {"messages": [AIMessage(content=response.content, name="researcher")]}


# ============================================================
# 编码 Agent - 计算和代码生成
# ============================================================
def coder_node(state: MultiAgentState) -> dict:
    """
    编码 Agent - 负责数学计算与代码生成

    工具集合：calculate

    Returns:
        dict: 状态更新字段（追加一条来自 coder 的 AIMessage）

    学习要点：
        - 工具集合按职责严格分离，避免"全能 Agent"导致 prompt 噪声。
    """
    logger.info("执行编码 Agent")

    messages = state.get("messages", [])
    llm = get_llm()

    # 绑定计算类工具
    coder_tools = [calculate]
    llm_with_tools = llm.bind_tools(coder_tools)

    system_msg = SystemMessage(content=(
        "你是一个编码和计算助手。你的职责是解决数学问题和生成代码。\n"
        "请使用计算工具来处理数学表达式。\n"
        "回答要精确、有步骤。"
    ))

    response = llm_with_tools.invoke([system_msg] + messages)
    logger.info("编码 Agent 完成")

    return {"messages": [AIMessage(content=response.content, name="coder")]}


# ============================================================
# 总结 Agent - 汇总和整理
# ============================================================
def summarizer_node(state: MultiAgentState) -> dict:
    """
    总结 Agent - 汇总结果并产出最终回复

    工具集合：无（不调用任何工具，专注整合信息）

    Returns:
        dict: 状态更新字段
            - messages    : 追加 summarizer 自己的 AIMessage
            - final_result: 最终回复文本（供 API 层直接返回）

    学习要点：
        - summarizer 是图的标准"收口节点"，负责把零散结果整合为最终答案。
        - 同时写入 messages（保留完整链路）和 final_result（方便调用方）。
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
    logger.info("总结 Agent 完成")

    return {
        "messages": [AIMessage(content=response.content, name="summarizer")],
        "final_result": response.content,
    }
