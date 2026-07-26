# -*- coding: utf-8 -*-
"""
Agent 服务层

封装 Agent 调用逻辑
"""

from typing import AsyncGenerator, Dict, List
from langchain_core.messages import HumanMessage, AIMessage

from app.agent.graph import agent_graph
from app.memory import memory_manager
from app.schemas.chat import ChatRequest
from app.core.logging import get_logger

logger = get_logger(__name__)


class AgentService:
    """Agent 服务类"""
    
    @staticmethod
    async def chat(request: ChatRequest, conversation_id: str) -> Dict:
        """
        阻塞式对话
        
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
        流式对话
        
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


# 全局服务实例
agent_service = AgentService()
