# -*- coding: utf-8 -*-
"""
流式服务

提供流式响应功能：
1. 基础对话流式输出（StreamService.stream_chat）
2. 工具调用流式通知

学习要点：
1. 使用 FastAPI 的 StreamingResponse
2. 使用 SSE (Server-Sent Events) 协议
3. 实时推送执行进度

历史说明：
    原 stream_advanced()（subgraph/parallel/mapreduce demo 图流式）
    随 app/agent/advanced 目录整体下线，无外部调用方，一并删除。
"""

import json
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage

from app.agent import agent_graph
from app.core.logging import get_logger

logger = get_logger(__name__)


class StreamService:
    """
    流式服务
    
    提供流式响应功能，将 Agent 执行过程实时推送给客户端。
    
    使用示例：
        service = StreamService()
        async for chunk in service.stream_chat("你好", "conv-123"):
            print(chunk)
    """
    
    @staticmethod
    async def stream_chat(message: str, conversation_id: str) -> AsyncGenerator[str, None]:
        """
        流式对话
        
        使用基础 Agent 图进行流式对话。
        
        Args:
            message: 用户消息
            conversation_id: 对话 ID
        
        Yields:
            str: SSE 格式的响应块
        """
        try:
            logger.info(f"开始流式对话: {message[:50]}...")
            
            # 构造初始状态
            initial_state = {
                "messages": [HumanMessage(content=message)],
                "tool_calls": [],
                "current_step": "start",
            }
            
            config = {
                "configurable": {
                    "thread_id": conversation_id
                }
            }
            
            # 使用 astream_events 获取流式事件
            async for event in agent_graph.astream_events(initial_state, config, version="v1"):
                event_kind = event["event"]
                
                # LLM 流式输出
                if event_kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if hasattr(chunk, "content") and chunk.content:
                        yield StreamService._format_sse({
                            "type": "content",
                            "content": chunk.content
                        })
                
                # 工具调用开始
                elif event_kind == "on_tool_start":
                    tool_name = event["name"]
                    yield StreamService._format_sse({
                        "type": "tool_call",
                        "content": f"正在调用工具: {tool_name}"
                    })
                
                # 工具调用结束
                elif event_kind == "on_tool_end":
                    tool_name = event["name"]
                    result = event["data"].get("output", "")
                    yield StreamService._format_sse({
                        "type": "tool_result",
                        "content": f"工具 {tool_name} 执行完成",
                        "result": str(result)[:200]  # 限制长度
                    })
            
            # 发送结束标记
            yield StreamService._format_sse({
                "type": "done",
                "content": "完成"
            })
        
        except Exception as e:
            logger.error(f"流式对话失败: {e}")
            yield StreamService._format_sse({
                "type": "error",
                "content": f"错误: {str(e)}"
            })
    
    @staticmethod
    def _format_sse(data: dict) -> str:
        """
        格式化 SSE 数据
        
        Args:
            data: 数据字典
        
        Returns:
            str: SSE 格式字符串
        
        学习要点：
        SSE 格式：
            data: {"type": "content", "content": "..."}\n\n
        """
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
