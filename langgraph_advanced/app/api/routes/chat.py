# -*- coding: utf-8 -*-
"""
基础对话路由

提供基础的 Agent 对话接口。
支持单 Agent、多 Agent、统一大图三种模式。
支持流式（SSE）和阻塞两种响应方式。

接口参数：
- mode: single / multi / master
- stream: true(流式) / false(阻塞，默认)
"""

import json
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, AIMessage

from app.agent.graph import agent_graph
from app.agent.multi_graph import multi_agent_graph
from app.agent.master_graph import master_graph
from app.schemas.chat import ChatRequest, ChatResponse
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


# ============================================================
# 流式响应生成器
# ============================================================

async def generate_stream_response(graph, initial_state: dict, config: dict, mode: str):
    """
    流式响应生成器
    
    使用 astream_events 实时推送节点执行状态和 LLM 输出。
    
    Args:
        graph: LangGraph 图实例
        initial_state: 初始状态
        config: 配置（包含 thread_id）
        mode: 运行模式
    
    Yields:
        SSE 格式的事件数据
    """
    try:
        # 发送开始事件
        yield f"data: {json.dumps({'type': 'start', 'mode': mode})}\n\n"
        
        # 使用 astream_events 获取实时事件
        async for event in graph.astream_events(initial_state, config, version="v2"):
            event_kind = event.get("event", "")
            
            # 节点开始事件
            if event_kind == "on_chain_start":
                node_name = event.get("name", "unknown")
                yield f"data: {json.dumps({'type': 'node_start', 'node': node_name})}\n\n"
            
            # 节点结束事件
            elif event_kind == "on_chain_end":
                node_name = event.get("name", "unknown")
                yield f"data: {json.dumps({'type': 'node_end', 'node': node_name})}\n\n"
            
            # LLM 流式输出
            elif event_kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk", None)
                if chunk and hasattr(chunk, "content") and chunk.content:
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk.content})}\n\n"
            
            # 工具调用事件
            elif event_kind == "on_tool_start":
                tool_name = event.get("name", "unknown")
                yield f"data: {json.dumps({'type': 'tool_call', 'tool': tool_name})}\n\n"
        
        # 发送结束事件
        yield f"data: {json.dumps({'type': 'end'})}\n\n"
    
    except Exception as e:
        logger.error(f"流式响应错误: {e}")
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"


# ============================================================
# 主对话接口
# ============================================================

@router.post("/chat")
async def chat(
    request: ChatRequest,
    mode: str = Query("single", description="模式: single(单Agent) / multi(多Agent协作) / master(统一大图)"),
    stream: bool = Query(False, description="是否流式响应: true(SSE流式) / false(阻塞，默认)")
):
    """
    基础对话接口
    
    支持三种模式：
    - single: 单 Agent 模式（默认）
    - multi: 多 Agent 协作模式
    - master: 统一大图模式（集成所有高级功能）
    
    Args:
        request: 对话请求（包含 message 和 conversation_id）
        mode: 运行模式（single / multi / master）
    
    Returns:
        ChatResponse: 对话响应
    """
    try:
        logger.info(f"收到对话请求: {request.message[:50]}... (模式: {mode}, 流式: {stream})")
        
        # 根据模式选择图和构建初始状态
        if mode == "master":
            graph = master_graph
            initial_state = {
                "messages": [HumanMessage(content=request.message)],
                "query": request.message,
                "conversation_id": request.conversation_id,
                "input_safe": True,
                "output_safe": True,
                "guard_warnings": [],
                "task_analysis": None,
                "next_route": None,
                "research_result": None,
                "research_sources": [],
                "document": None,
                "chunks": [],
                "chunk_summaries": [],
                "final_summary": None,
                "parallel_tasks": [],
                "worker_results": [],
                "aggregated_result": None,
                "selected_tools": [],
                "tool_results": {},
                "mcp_tool_calls": [],
                "mcp_results": [],
                "pending_action": None,
                "human_feedback": None,
                "approved": False,
                "reflection": None,
                "retry_count": 0,
                "max_retries": 3,
                "final_response": None,
            }
        
        elif mode == "multi":
            graph = multi_agent_graph
            initial_state = {
                "messages": [HumanMessage(content=request.message)],
                "next_agent": None,
                "final_result": None,
            }
        
        else:  # single
            graph = agent_graph
            initial_state = {
                "messages": [HumanMessage(content=request.message)],
                "tool_calls": [],
                "current_step": "start",
            }
        
        # 配置（用于记忆持久化）
        config = {
            "configurable": {
                "thread_id": request.conversation_id
            }
        }
        
        # ============================================================
        # 流式/阻塞 切换
        # ============================================================
        
        if stream:
            # 流式模式：返回 SSE 流
            logger.info("使用流式响应")
            return StreamingResponse(
                generate_stream_response(graph, initial_state, config, mode),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
                }
            )
        
        else:
            # 阻塞模式：等待完成后返回 JSON
            logger.info("使用阻塞响应")
            result = await graph.ainvoke(initial_state, config)
            
            # 根据模式提取响应
            if mode == "master":
                response_text = result.get("final_response") or "处理完成"
                tool_calls = list(result.get("tool_results", {}).keys())
            
            elif mode == "multi":
                messages = result.get("messages", [])
                response_text = result.get("final_result") or (
                    messages[-1].content if messages else "抱歉，我没有理解。"
                )
                tool_calls = []
            
            else:  # single
                messages = result.get("messages", [])
                response_text = messages[-1].content if messages else "抱歉，我没有理解。"
                tool_calls = result.get("tool_calls", [])
            
            return ChatResponse(
                response=response_text,
                conversation_id=request.conversation_id,
                tool_calls=tool_calls
            )
    
    except Exception as e:
        logger.error(f"对话处理失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
