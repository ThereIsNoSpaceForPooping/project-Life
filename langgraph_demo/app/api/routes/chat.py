# -*- coding: utf-8 -*-
"""
对话路由

提供阻塞式和流式对话接口
"""

import json
import uuid
from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse

from app.schemas.chat import ChatRequest, ChatResponse, StreamChunk
from app.services import agent_service
from app.core.logging import get_logger

logger = get_logger(__name__)

chat_router = APIRouter()


@chat_router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    conversation_id: str = Header(None, alias="X-Conversation-ID")
):
    """
    阻塞式对话接口
    
    - 等待 Agent 完整执行后返回结果
    - 支持对话记忆（通过 conversation_id）
    """
    # 如果没有提供 conversation_id，生成一个
    if not conversation_id:
        conversation_id = str(uuid.uuid4())
    
    logger.info(f"收到对话请求，conversation_id: {conversation_id}")
    
    # 调用服务
    result = await agent_service.chat(request, conversation_id)
    
    return ChatResponse(
        content=result["content"],
        tool_calls=result.get("tool_calls"),
        finish_reason=result.get("finish_reason", "complete"),
    )


@chat_router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    conversation_id: str = Header(None, alias="X-Conversation-ID")
):
    """
    流式对话接口
    
    - 实时推送 Agent 执行过程
    - 支持对话记忆（通过 conversation_id）
    - SSE (Server-Sent Events) 格式
    """
    # 如果没有提供 conversation_id，生成一个
    if not conversation_id:
        conversation_id = str(uuid.uuid4())
    
    logger.info(f"收到流式对话请求，conversation_id: {conversation_id}")
    
    async def generate():
        """生成 SSE 数据流"""
        try:
            async for chunk in agent_service.chat_stream(request, conversation_id):
                # 转换为 StreamChunk 模型
                stream_chunk = StreamChunk(**chunk)
                # 序列化为 JSON
                data = json.dumps(stream_chunk.dict(), ensure_ascii=False)
                # SSE 格式
                yield f"data: {data}\n\n"
            
            # 发送结束标记
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            logger.error(f"流式对话错误: {e}")
            error_chunk = StreamChunk(
                type="error",
                content=str(e),
            )
            yield f"data: {json.dumps(error_chunk.dict(), ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Conversation-ID": conversation_id,
        }
    )
