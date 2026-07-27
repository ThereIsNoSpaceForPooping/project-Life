# -*- coding: utf-8 -*-
"""
FastAPI Demo - 异步和流式接口演示

展示 FastAPI 的异步能力和 SSE (Server-Sent Events) 流式推送
"""

import asyncio
import json
from datetime import datetime
from typing import AsyncGenerator

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


# ============================================================
# 异步接口演示
# ============================================================

@router.get("/async/demo")
async def async_demo(
    task: str = Query("default", description="任务名称"),
    delay: float = Query(1.0, ge=0.1, le=10.0, description="模拟延迟(秒)")
):
    """
    异步接口演示
    
    - 使用 async/await 语法
    - 非阻塞 I/O 操作
    - 可以并发处理多个请求
    """
    logger.info(f"开始异步任务: {task}, 延迟: {delay}s")
    
    # 模拟异步 I/O 操作（如数据库查询、API 调用）
    start_time = datetime.now()
    await asyncio.sleep(delay)
    end_time = datetime.now()
    
    return {
        "task": task,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "duration": (end_time - start_time).total_seconds(),
        "message": f"异步任务 '{task}' 完成"
    }


@router.get("/async/concurrent")
async def async_concurrent(
    count: int = Query(3, ge=1, le=10, description="并发任务数")
):
    """
    并发任务演示
    
    - 使用 asyncio.gather 并发执行多个异步任务
    - 总耗时 ≈ 最慢任务的耗时（而非所有任务耗时之和）
    """
    logger.info(f"开始 {count} 个并发任务")
    
    async def task(i: int):
        """单个异步任务"""
        start = datetime.now()
        await asyncio.sleep(i * 0.5)  # 每个任务不同延迟
        end = datetime.now()
        return {
            "task_id": i,
            "duration": (end - start).total_seconds(),
            "result": f"任务 {i} 完成"
        }
    
    # 并发执行所有任务
    start_time = datetime.now()
    results = await asyncio.gather(*[task(i) for i in range(1, count + 1)])
    total_time = (datetime.now() - start_time).total_seconds()
    
    return {
        "total_tasks": count,
        "total_time": total_time,
        "results": results,
        "message": f"{count} 个任务并发完成，总耗时 {total_time:.2f}s"
    }


# ============================================================
# 流式接口演示 (SSE - Server-Sent Events)
# ============================================================

async def generate_stream(message: str, interval: float, count: int) -> AsyncGenerator[str, None]:
    """
    生成 SSE 数据流
    
    SSE 格式:
        data: {"content": "..."}\n\n
        data: {"content": "..."}\n\n
        data: [DONE]\n\n
    """
    for i in range(1, count + 1):
        # 模拟逐字生成
        chunk = {
            "type": "content",
            "content": f"{message} [{i}/{count}]",
            "timestamp": datetime.now().isoformat()
        }
        
        # yield SSE 格式数据
        yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
        
        # 模拟生成延迟
        await asyncio.sleep(interval)
    
    # 发送结束标记
    yield "data: [DONE]\n\n"


@router.get("/stream/demo")
async def stream_demo(
    message: str = Query("Hello", description="消息内容"),
    interval: float = Query(0.5, ge=0.1, le=5.0, description="推送间隔(秒)"),
    count: int = Query(5, ge=1, le=20, description="推送次数")
):
    """
    流式接口演示 (SSE)
    
    - 使用 StreamingResponse 返回流式数据
    - 客户端可以实时接收数据
    - 适用于 AI 对话、实时通知等场景
    """
    logger.info(f"开始流式推送: message={message}, interval={interval}s, count={count}")
    
    return StreamingResponse(
        generate_stream(message, interval, count),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        }
    )


async def generate_chat_stream(messages: list) -> AsyncGenerator[str, None]:
    """
    模拟 AI 对话流式响应
    
    模拟真实 AI 对话的流式输出：
    1. 思考中...
    2. 逐字输出回答
    3. 完成
    """
    # 1. 发送思考状态
    yield f"data: {json.dumps({'type': 'thinking', 'content': '正在思考...'}, ensure_ascii=False)}\n\n"
    await asyncio.sleep(0.5)
    
    # 2. 模拟逐字生成回答
    response = "这是一个模拟的 AI 回答。FastAPI 的流式接口可以让客户端实时接收数据，提供更好的用户体验。"
    
    for char in response:
        chunk = {
            "type": "content",
            "content": char,
        }
        yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.05)  # 模拟逐字生成延迟
    
    # 3. 发送完成标记
    yield f"data: {json.dumps({'type': 'done', 'content': '完成'}, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"


@router.post("/stream/chat")
async def stream_chat():
    """
    模拟 AI 对话流式接口
    
    POST 请求体:
    {
        "messages": [
            {"role": "user", "content": "你好"}
        ]
    }
    """
    logger.info("开始 AI 对话流式响应")
    
    return StreamingResponse(
        generate_chat_stream([]),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


# ============================================================
# 混合接口演示（异步 + 流式）
# ============================================================

async def generate_progress_stream(total_steps: int, step_delay: float) -> AsyncGenerator[str, None]:
    """
    生成进度流
    
    模拟长时间任务的进度推送
    """
    for step in range(1, total_steps + 1):
        progress = {
            "type": "progress",
            "step": step,
            "total": total_steps,
            "percent": round(step / total_steps * 100, 1),
            "message": f"步骤 {step}/{total_steps} 完成",
            "timestamp": datetime.now().isoformat()
        }
        
        yield f"data: {json.dumps(progress, ensure_ascii=False)}\n\n"
        
        # 模拟每个步骤的处理时间
        await asyncio.sleep(step_delay)
    
    # 完成
    yield f"data: {json.dumps({'type': 'complete', 'message': '所有步骤完成'}, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"


@router.get("/stream/progress")
async def stream_progress(
    steps: int = Query(5, ge=1, le=20, description="总步骤数"),
    delay: float = Query(1.0, ge=0.1, le=5.0, description="每步延迟(秒)")
):
    """
    进度流演示
    
    - 模拟长时间任务的进度推送
    - 客户端可以实时显示进度条
    - 适用于文件上传、数据处理等场景
    """
    logger.info(f"开始进度流: steps={steps}, delay={delay}s")
    
    return StreamingResponse(
        generate_progress_stream(steps, delay),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )
