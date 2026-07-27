# -*- coding: utf-8 -*-
"""
Agent 服务层

封装 Agent 调用逻辑，支持：
  - 单 Agent 对话（阻塞/流式）
  - 多 Agent 协作对话（阻塞/流式）
"""

from typing import AsyncGenerator, Dict, List
from langchain_core.messages import HumanMessage, AIMessage

from app.agent.graph import agent_graph
from app.agent.multi_graph import multi_agent_graph
from app.memory import memory_manager
from app.schemas.chat import ChatRequest
from app.core.logging import get_logger

logger = get_logger(__name__)


class AgentService:
    """Agent 服务类"""
    
    # ============================================================
    # 单 Agent 模式
    # ============================================================
    @staticmethod
    async def chat(request: ChatRequest, conversation_id: str) -> Dict:
        """
        阻塞式对话（单 Agent）
        
        Args:
            request: 对话请求
            conversation_id: 对话 ID
            
        Returns:
            Dict: 对话响应
        """
        logger.info(f"处理对话请求，conversation_id: {conversation_id}")
        
        # 构造初始状态
        messages = [HumanMessage(content=msg.content) for msg in request.messages]
        
        initial_state = {
            "messages": messages,
            "conversation_id": conversation_id,
            "tool_calls": [],
            "current_step": None,
        }
        
        # 获取记忆配置
        config = memory_manager.get_config(conversation_id)
        
        # 执行图
        result = await agent_graph.ainvoke(
            initial_state,
            config=config
        )
        
        # 提取最终回复
        final_messages = result.get("messages", [])
        final_content = ""
        if final_messages:
            last_msg = final_messages[-1]
            if isinstance(last_msg, AIMessage):
                final_content = last_msg.content
        
        return {
            "content": final_content,
            "tool_calls": result.get("tool_calls", []),
            "finish_reason": "complete",
        }
    
    @staticmethod
    async def chat_stream(request: ChatRequest, conversation_id: str) -> AsyncGenerator[Dict, None]:
        """
        流式对话（单 Agent）
        
        Args:
            request: 对话请求
            conversation_id: 对话 ID
            
        Yields:
            Dict: 流式数据块
        """
        logger.info(f"处理流式对话请求，conversation_id: {conversation_id}")
        
        # 构造初始状态
        messages = [HumanMessage(content=msg.content) for msg in request.messages]
        
        initial_state = {
            "messages": messages,
            "conversation_id": conversation_id,
            "tool_calls": [],
            "current_step": None,
        }
        
        # 获取记忆配置
        config = memory_manager.get_config(conversation_id)
        
        # 流式执行图
        async for event in agent_graph.astream_events(
            initial_state,
            config=config,
            version="v1"
        ):
            event_kind = event.get("event")
            
            # LLM 流式输出
            if event_kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    yield {
                        "type": "content",
                        "content": chunk.content,
                    }
            
            # 工具调用开始
            elif event_kind == "on_tool_start":
                tool_name = event.get("name")
                tool_input = event.get("data", {}).get("input")
                yield {
                    "type": "tool_call",
                    "content": f"调用工具: {tool_name}",
                    "metadata": {"tool": tool_name, "input": tool_input},
                }
            
            # 工具调用结束
            elif event_kind == "on_tool_end":
                tool_output = event.get("data", {}).get("output")
                yield {
                    "type": "tool_result",
                    "content": str(tool_output),
                }

    # ============================================================
    # 多 Agent 协作模式
    # ============================================================
    @staticmethod
    async def chat_multi(request: ChatRequest, conversation_id: str) -> Dict:
        """
        阻塞式对话（多 Agent 协作）
        
        流程: 路由器 → 专业Agent → 总结Agent
        
        Args:
            request: 对话请求
            conversation_id: 对话 ID
            
        Returns:
            Dict: 对话响应
        """
        logger.info(f"处理多Agent对话请求，conversation_id: {conversation_id}")
        
        # 构造初始状态
        messages = [HumanMessage(content=msg.content) for msg in request.messages]
        
        initial_state = {
            "messages": messages,
            "next_agent": None,
            "final_result": None,
        }
        
        # 执行多 Agent 图
        result = await multi_agent_graph.ainvoke(initial_state)
        
        # 提取最终结果
        final_content = result.get("final_result", "")
        if not final_content:
            # 从消息列表中提取最后一条 AI 消息
            for msg in reversed(result.get("messages", [])):
                if isinstance(msg, AIMessage) and msg.content:
                    final_content = msg.content
                    break
        
        return {
            "content": final_content,
            "tool_calls": [],
            "finish_reason": "complete",
        }
    
    @staticmethod
    async def chat_stream_multi(request: ChatRequest, conversation_id: str) -> AsyncGenerator[Dict, None]:
        """
        流式对话（多 Agent 协作）
        
        实时推送每个 Agent 的执行过程
        
        Args:
            request: 对话请求
            conversation_id: 对话 ID
            
        Yields:
            Dict: 流式数据块
        """
        logger.info(f"处理多Agent流式对话请求，conversation_id: {conversation_id}")
        
        # 构造初始状态
        messages = [HumanMessage(content=msg.content) for msg in request.messages]
        
        initial_state = {
            "messages": messages,
            "next_agent": None,
            "final_result": None,
        }
        
        # 流式执行多 Agent 图
        async for event in multi_agent_graph.astream_events(
            initial_state,
            version="v1"
        ):
            event_kind = event.get("event")
            
            # 节点开始执行
            if event_kind == "on_chain_start":
                node_name = event.get("name", "")
                if node_name in ("router", "researcher", "coder", "summarizer"):
                    agent_labels = {
                        "router": "🔀 路由器",
                        "researcher": "🔍 研究Agent",
                        "coder": "💻 编码Agent",
                        "summarizer": "📝 总结Agent",
                    }
                    yield {
                        "type": "tool_call",
                        "content": f"{agent_labels.get(node_name, node_name)} 开始执行",
                        "metadata": {"agent": node_name},
                    }
            
            # LLM 流式输出
            elif event_kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    yield {
                        "type": "content",
                        "content": chunk.content,
                    }
            
            # 工具调用
            elif event_kind == "on_tool_start":
                tool_name = event.get("name")
                yield {
                    "type": "tool_call",
                    "content": f"调用工具: {tool_name}",
                    "metadata": {"tool": tool_name},
                }
            
            elif event_kind == "on_tool_end":
                tool_output = event.get("data", {}).get("output")
                yield {
                    "type": "tool_result",
                    "content": str(tool_output),
                }


# 全局服务实例
agent_service = AgentService()
