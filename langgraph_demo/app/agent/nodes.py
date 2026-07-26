# -*- coding: utf-8 -*-
"""
Agent 节点定义

定义 LangGraph 图中的各个节点
"""

from typing import List
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.agent.state import AgentState
from app.agent.tools import TOOLS
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def get_llm(provider: str = None, model: str = None, temperature: float = None) -> ChatOpenAI:
    """
    获取 LLM 实例
    
    Args:
        provider: LLM 提供商
        model: 模型名称
        temperature: 温度参数
        
    Returns:
        ChatOpenAI: LLM 实例
    """
    provider = provider or settings.DEFAULT_PROVIDER
    temperature = temperature if temperature is not None else settings.TEMPERATURE
    
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


def agent_node(state: AgentState) -> dict:
    """
    Agent 节点 - 调用 LLM 进行推理
    
    Args:
        state: 当前状态
        
    Returns:
        dict: 更新后的状态
    """
    logger.info("执行 Agent 节点")
    
    # 获取消息列表
    messages = state.get("messages", [])
    
    # 获取 LLM（这里使用默认配置，实际可以从 state 中获取）
    llm = get_llm()
    
    # 绑定工具
    llm_with_tools = llm.bind_tools(TOOLS)
    
    # 调用 LLM
    response = llm_with_tools.invoke(messages)
    
    # 记录工具调用
    tool_calls = []
    if hasattr(response, "tool_calls") and response.tool_calls:
        tool_calls = [
            {
                "name": tc["name"],
                "args": tc["args"],
            }
            for tc in response.tool_calls
        ]
        logger.info(f"LLM 请求调用工具: {tool_calls}")
    
    return {
        "messages": [response],
        "tool_calls": tool_calls,
        "current_step": "agent",
    }


def tool_node(state: AgentState) -> dict:
    """
    工具节点 - 执行工具调用
    
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
            continue
        
        # 执行工具
        try:
            result = tool.invoke(tool_args)
            logger.info(f"工具 {tool_name} 执行结果: {result}")
            tool_results.append({
                "tool_call_id": tool_call["id"],
                "name": tool_name,
                "content": str(result),
            })
        except Exception as e:
            logger.error(f"工具执行失败: {e}")
            tool_results.append({
                "tool_call_id": tool_call["id"],
                "name": tool_name,
                "content": f"错误: {str(e)}",
            })
    
    # 构造 ToolMessage 列表
    from langchain_core.messages import ToolMessage
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


def should_continue(state: AgentState) -> str:
    """
    判断是否继续执行工具
    
    Args:
        state: 当前状态
        
    Returns:
        str: 下一个节点名称
    """
    messages = state.get("messages", [])
    last_message = messages[-1] if messages else None
    
    # 如果最后一条消息有工具调用，继续执行工具
    if last_message and hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    
    # 否则结束
    return "end"
