# -*- coding: utf-8 -*-
"""
Agent 节点定义

定义 LangGraph 图中的各个节点
包含：推理节点、工具节点（带重试）、人机协作节点
"""

import time
from typing import List, Optional
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

from app.agent.state import AgentState
from app.agent.tools import TOOLS
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


# ============================================================
# LLM 实例管理
# ============================================================
def get_llm(provider: str = None, model: str = None, temperature: float = None) -> ChatOpenAI:
    """
    获取 LLM 实例

    Args:
        provider: LLM 提供商（minimax / dashscope）
        model: 模型名称（不指定则使用默认模型）
        temperature: 温度参数

    Returns:
        ChatOpenAI: LLM 实例
    """
    provider = provider or settings.DEFAULT_PROVIDER
    temperature = temperature if temperature is not None else settings.TEMPERATURE

    # 根据 provider 选择对应配置
    if provider == "minimax":
        return ChatOpenAI(
            model=model or settings.MINIMAX_MODEL,
            api_key=settings.MINIMAX_API_KEY,
            base_url=settings.MINIMAX_BASE_URL,
            temperature=temperature,
            streaming=True,
        )
    elif provider == "dashscope":
        return ChatOpenAI(
            model=model or settings.DASHSCOPE_MODEL,
            api_key=settings.DASHSCOPE_API_KEY,
            base_url=settings.DASHSCOPE_BASE_URL,
            temperature=temperature,
            streaming=True,
        )
    else:
        raise ValueError(f"不支持的 provider: {provider}")


# ============================================================
# 节点1: Agent 推理节点
# ============================================================
def agent_node(state: AgentState) -> dict:
    """
    Agent 节点 - 调用 LLM 进行推理

    流程:
        1. 从 state 获取消息列表
        2. 创建 LLM 并绑定工具
        3. 调用 LLM 生成响应
        4. 如果 LLM 返回 tool_calls，后续会路由到工具节点
        5. 如果没有 tool_calls，后续会路由到 END

    Args:
        state: 当前状态

    Returns:
        dict: 更新后的状态
    """
    logger.info("执行 Agent 节点")

    # 获取消息列表
    messages = state.get("messages", [])

    # 获取 LLM 并绑定工具
    llm = get_llm()
    llm_with_tools = llm.bind_tools(TOOLS)

    # 调用 LLM
    response = llm_with_tools.invoke(messages)

    # 记录工具调用
    tool_calls = []
    if hasattr(response, "tool_calls") and response.tool_calls:
        tool_calls = [
            {"name": tc["name"], "args": tc["args"]}
            for tc in response.tool_calls
        ]
        logger.info(f"LLM 请求调用工具: {tool_calls}")

    return {
        "messages": [response],
        "tool_calls": tool_calls,
        "current_step": "agent",
    }


# ============================================================
# 节点2: 工具执行节点（带重试机制）
# ============================================================

# 重试配置
MAX_RETRIES = 3           # 最大重试次数
RETRY_DELAY = 1.0         # 重试间隔（秒）
RETRY_BACKOFF = 2.0       # 退避倍数（指数退避）


def _execute_tool_with_retry(tool, tool_args: dict, tool_name: str) -> str:
    """
    带重试机制的工具执行

    采用指数退避策略：
        第1次失败 → 等待 1s → 重试
        第2次失败 → 等待 2s → 重试
        第3次失败 → 返回错误

    Args:
        tool: 工具实例
        tool_args: 工具参数
        tool_name: 工具名称

    Returns:
        str: 工具执行结果
    """
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = tool.invoke(tool_args)
            logger.info(f"工具 {tool_name} 第{attempt}次执行成功")
            return str(result)

        except Exception as e:
            last_error = e
            logger.warning(
                f"工具 {tool_name} 第{attempt}次执行失败: {e}"
            )

            # 如果还有重试机会，等待后重试
            if attempt < MAX_RETRIES:
                delay = RETRY_DELAY * (RETRY_BACKOFF ** (attempt - 1))
                logger.info(f"等待 {delay}s 后重试...")
                time.sleep(delay)

    # 所有重试都失败
    logger.error(f"工具 {tool_name} 在 {MAX_RETRIES} 次尝试后仍然失败")
    return f"工具执行失败（已重试{MAX_RETRIES}次）: {str(last_error)}"


def tool_node(state: AgentState) -> dict:
    """
    工具节点 - 执行工具调用（带重试）

    流程:
        1. 从最后一条 AIMessage 获取 tool_calls
        2. 遍历每个 tool_call，查找对应工具
        3. 使用重试机制执行工具
        4. 构造 ToolMessage 列表返回

    Args:
        state: 当前状态

    Returns:
        dict: 更新后的状态
    """
    logger.info("执行工具节点")

    # 获取最后一条消息（应该是 AIMessage 带 tool_calls）
    messages = state.get("messages", [])
    last_message = messages[-1] if messages else None

    if not last_message or not hasattr(last_message, "tool_calls"):
        logger.error("工具节点未找到有效的 tool_calls")
        return {"current_step": "tool_error"}

    # 执行每个工具调用
    tool_results = []
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]

        # 查找工具
        tool = next((t for t in TOOLS if t.name == tool_name), None)
        if not tool:
            logger.error(f"未找到工具: {tool_name}")
            tool_results.append({
                "tool_call_id": tool_call["id"],
                "name": tool_name,
                "content": f"错误: 未找到工具 '{tool_name}'",
            })
            continue

        # 带重试的工具执行
        result = _execute_tool_with_retry(tool, tool_args, tool_name)
        logger.info(f"工具 {tool_name} 最终结果: {result}")

        tool_results.append({
            "tool_call_id": tool_call["id"],
            "name": tool_name,
            "content": result,
        })

    # 构造 ToolMessage 列表
    tool_messages = [
        ToolMessage(
            content=tr["content"],
            tool_call_id=tr["tool_call_id"],
            name=tr["name"],
        )
        for tr in tool_results
    ]

    return {
        "messages": tool_messages,
        "current_step": "tool",
    }


# ============================================================
# 节点3: 人机协作节点（Human-in-the-Loop）
# ============================================================
def human_review_node(state: AgentState) -> dict:
    """
    人机协作节点 - 等待人工审核

    当 Agent 需要执行敏感操作时，暂停执行等待人工确认。
    配合 LangGraph 的 interrupt_before 使用。

    流程:
        1. 检查 state 中是否有待审核的工具调用
        2. 如果有，标记为需要审核
        3. 人工审核后，通过 Command(resume=...) 恢复执行

    Args:
        state: 当前状态

    Returns:
        dict: 更新后的状态
    """
    logger.info("执行人机协作节点 - 等待人工审核")

    messages = state.get("messages", [])
    last_message = messages[-1] if messages else None

    # 检查是否需要人工审核
    if last_message and hasattr(last_message, "tool_calls") and last_message.tool_calls:
        # 标记需要审核的工具调用
        pending_tools = [tc["name"] for tc in last_message.tool_calls]
        logger.info(f"等待人工审核工具调用: {pending_tools}")

        return {
            "current_step": "human_review",
            "messages": [
                AIMessage(
                    content=f"⚠️ 需要人工确认以下操作: {', '.join(pending_tools)}"
                )
            ],
        }

    return {"current_step": "human_review_passed"}


# ============================================================
# 路由函数
# ============================================================
def should_continue(state: AgentState) -> str:
    """
    判断是否继续执行工具

    路由规则:
        - 有 tool_calls → 路由到 "tools" 节点
        - 无 tool_calls → 路由到 "end" 结束

    Args:
        state: 当前状态

    Returns:
        str: 下一个节点名称 ("tools" 或 "end")
    """
    messages = state.get("messages", [])
    last_message = messages[-1] if messages else None

    # 如果最后一条消息有工具调用，继续执行工具
    if last_message and hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"

    # 否则结束
    return "end"


def should_review(state: AgentState) -> str:
    """
    判断是否需要人工审核

    路由规则:
        - 有 tool_calls 且启用审核 → 路由到 "human_review"
        - 否则 → 路由到 "tools" 直接执行

    Args:
        state: 当前状态

    Returns:
        str: 下一个节点名称 ("human_review" 或 "tools")
    """
    messages = state.get("messages", [])
    last_message = messages[-1] if messages else None

    if last_message and hasattr(last_message, "tool_calls") and last_message.tool_calls:
        # 检查是否启用人工审核
        if settings.ENABLE_HUMAN_REVIEW:
            return "human_review"
        return "tools"

    return "end"
