# -*- coding: utf-8 -*-
"""
高级功能路由

提供 LangGraph 高级功能的 API 接口：
- 子图（Subgraph）
- 人机协作（Interrupt）
- 并行执行（Parallel）
- Map-Reduce
- 动态工具（Dynamic Tools）
"""

from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage

from app.agent.advanced.subgraph import research_graph
from app.agent.advanced.interrupt import interrupt_graph
from app.agent.advanced.parallel import parallel_graph
from app.agent.advanced.mapreduce import mapreduce_graph
from app.agent.advanced.dynamic_tools import dynamic_tools_graph
from app.schemas.chat import ChatRequest, ChatResponse
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post("/advanced/subgraph", response_model=ChatResponse)
async def subgraph_chat(request: ChatRequest):
    """
    子图对话接口
    
    使用研究子图处理用户消息。
    流程：search → analyze → compile_report
    """
    try:
        logger.info(f"子图对话请求: {request.message[:50]}...")
        
        initial_state = {
            "messages": [HumanMessage(content=request.message)],
            "query": request.message,
            "search_results": [],
            "analysis": None,
            "report": None,
        }
        
        config = {"configurable": {"thread_id": request.conversation_id}}
        result = research_graph.invoke(initial_state, config)
        
        messages = result.get("messages", [])
        response_text = messages[-1].content if messages else "研究完成。"
        
        return ChatResponse(
            response=response_text,
            conversation_id=request.conversation_id
        )
    
    except Exception as e:
        logger.error(f"子图处理失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/advanced/interrupt", response_model=ChatResponse)
async def interrupt_chat(request: ChatRequest):
    """
    人机协作对话接口
    
    使用 interrupt 机制处理用户消息。
    当需要工具调用时，会暂停等待人工确认。
    """
    try:
        logger.info(f"人机协作请求: {request.message[:50]}...")
        
        initial_state = {
            "messages": [HumanMessage(content=request.message)],
            "pending_action": None,
            "human_feedback": None,
            "approved": False,
        }
        
        config = {"configurable": {"thread_id": request.conversation_id}}
        result = interrupt_graph.invoke(initial_state, config)
        
        messages = result.get("messages", [])
        response_text = messages[-1].content if messages else "处理完成。"
        
        return ChatResponse(
            response=response_text,
            conversation_id=request.conversation_id
        )
    
    except Exception as e:
        logger.error(f"人机协作处理失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/advanced/parallel", response_model=ChatResponse)
async def parallel_chat(request: ChatRequest):
    """
    并行执行对话接口
    
    使用 Fan-out/Fan-in 模式并行处理多个任务。
    """
    try:
        logger.info(f"并行执行请求: {request.message[:50]}...")
        
        initial_state = {
            "messages": [HumanMessage(content=request.message)],
            "tasks": [],
            "worker_results": [],
            "final_result": None,
        }
        
        config = {"configurable": {"thread_id": request.conversation_id}}
        result = parallel_graph.invoke(initial_state, config)
        
        final_result = result.get("final_result", "并行处理完成。")
        
        return ChatResponse(
            response=final_result,
            conversation_id=request.conversation_id
        )
    
    except Exception as e:
        logger.error(f"并行执行失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/advanced/mapreduce", response_model=ChatResponse)
async def mapreduce_chat(request: ChatRequest):
    """
    Map-Reduce 对话接口
    
    使用 Map-Reduce 模式处理长文档。
    流程：split → map → reduce
    """
    try:
        logger.info(f"Map-Reduce 请求: {request.message[:50]}...")
        
        initial_state = {
            "messages": [HumanMessage(content=request.message)],
            "document": request.message,
            "chunks": [],
            "chunk_summaries": [],
            "final_summary": None,
        }
        
        config = {"configurable": {"thread_id": request.conversation_id}}
        result = mapreduce_graph.invoke(initial_state, config)
        
        final_summary = result.get("final_summary", "处理完成。")
        
        return ChatResponse(
            response=final_summary,
            conversation_id=request.conversation_id
        )
    
    except Exception as e:
        logger.error(f"Map-Reduce 处理失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/advanced/dynamic-tools", response_model=ChatResponse)
async def dynamic_tools_chat(request: ChatRequest):
    """
    动态工具对话接口
    
    根据用户意图动态选择工具。
    流程：intent_analyzer → tool_selector → agent → tools
    """
    try:
        logger.info(f"动态工具请求: {request.message[:50]}...")
        
        initial_state = {
            "messages": [HumanMessage(content=request.message)],
            "intent": None,
            "selected_tools": [],
            "current_tools": None,
        }
        
        config = {"configurable": {"thread_id": request.conversation_id}}
        result = dynamic_tools_graph.invoke(initial_state, config)
        
        messages = result.get("messages", [])
        response_text = messages[-1].content if messages else "处理完成。"
        
        return ChatResponse(
            response=response_text,
            conversation_id=request.conversation_id
        )
    
    except Exception as e:
        logger.error(f"动态工具处理失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
