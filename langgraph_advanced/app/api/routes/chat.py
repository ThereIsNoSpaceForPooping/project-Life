# -*- coding: utf-8 -*-
"""
基础对话路由

提供基础的 Agent 对话接口。
"""

from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage

from app.agent.graph import agent_graph
from app.schemas.chat import ChatRequest, ChatResponse
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    基础对话接口
    
    使用单 Agent 图处理用户消息。
    
    Args:
        request: 对话请求（包含 message 和 conversation_id）
    
    Returns:
        ChatResponse: 对话响应
    """
    try:
        logger.info(f"收到对话请求: {request.message[:50]}...")
        
        # 构造初始状态
        initial_state = {
            "messages": [HumanMessage(content=request.message)],
            "tool_calls": [],
            "current_step": "start",
        }
        
        # 配置（包含 thread_id 用于记忆）
        config = {
            "configurable": {
                "thread_id": request.conversation_id
            }
        }
        
        # 执行图
        result = agent_graph.invoke(initial_state, config)
        
        # 提取响应
        messages = result.get("messages", [])
        response_text = messages[-1].content if messages else "抱歉，我没有理解。"
        
        return ChatResponse(
            response=response_text,
            conversation_id=request.conversation_id,
            tool_calls=result.get("tool_calls", [])
        )
    
    except Exception as e:
        logger.error(f"对话处理失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
