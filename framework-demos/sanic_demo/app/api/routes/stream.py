# -*- coding: utf-8 -*-
"""
Sanic Demo - 异步和流式接口演示

展示 Sanic 的异步能力和 SSE (Server-Sent Events) 流式推送
"""

import asyncio
import json
from datetime import datetime

from sanic import Blueprint
from sanic.response import json as json_response
from sanic.response import StreamingHTTPResponse

from app.core.logging import get_logger

logger = get_logger(__name__)

bp = Blueprint("stream", url_prefix="/api/stream")


# ============================================================
# 异步接口演示
# ============================================================

@bp.get("/async/demo")
async def async_demo(request):
    """
    异步接口演示
    
    - 使用 async/await 语法
    - 非阻塞 I/O 操作
    - 可以并发处理多个请求
    """
    # 从查询参数获取配置
    task = request.args.get("task", "default")
    delay = float(request.args.get("delay", 1.0))
    
    # 限制参数范围
    delay = max(0.1, min(10.0, delay))
    
    logger.info(f"开始异步任务: {task}, 延迟: {delay}s")
    
    # 模拟异步 I/O 操作（如数据库查询、API 调用）
    start_time = datetime.now()
    await asyncio.sleep(delay)
    end_time = datetime.now()
    
    return json_response({
        "task": task,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "duration": (end_time - start_time).total_seconds(),
        "message": f"异步任务 '{task}' 完成"
    })


@bp.get("/async/concurrent")
async def async_concurrent(request):
    """
    并发任务演示
    
    - 使用 asyncio.gather 并发执行多个异步任务
    - 总耗时 ≈ 最慢任务的耗时（而非所有任务耗时之和）
    """
    # 从查询参数获取并发数
    count = int(request.args.get("count", 3))
    count = max(1, min(10, count))
    
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
    
    return json_response({
        "total_tasks": count,
        "total_time": total_time,
        "results": results,
        "message": f"{count} 个任务并发完成，总耗时 {total_time:.2f}s"
    })


# ============================================================
# 流式接口演示 (SSE - Server-Sent Events)
# ============================================================

@bp.get("/stream/demo")
async def stream_demo(request):
    """
    流式接口演示 (SSE)
    
    - 使用 StreamingHTTPResponse 返回流式数据
    - 客户端可以实时接收数据
    - 适用于 AI 对话、实时通知等场景
    """
    # 从查询参数获取配置
    message = request.args.get("message", "Hello")
    interval = float(request.args.get("interval", 0.5))
    count = int(request.args.get("count", 5))
    
    # 限制参数范围
    interval = max(0.1, min(5.0, interval))
    count = max(1, min(20, count))
    
    logger.info(f"开始流式推送: message={message}, interval={interval}s, count={count}")
    
    async def generate_stream(response):
        """生成 SSE 数据流"""
        for i in range(1, count + 1):
            # 模拟逐字生成
            chunk = {
                "type": "content",
                "content": f"{message} [{i}/{count}]",
                "timestamp": datetime.now().isoformat()
            }
            
            # 写入 SSE 格式数据
            await response.write(f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n")
            
            # 模拟生成延迟
            await asyncio.sleep(interval)
        
        # 发送结束标记
        await response.write("data: [DONE]\n\n")
    
    return StreamingHTTPResponse(
        generate_stream,
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@bp.post("/stream/chat")
async def stream_chat(request):
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
    
    async def generate_chat_stream(response):
        """模拟 AI 对话流式响应"""
        # 1. 发送思考状态
        await response.write(f"data: {json.dumps({'type': 'thinking', 'content': '正在思考...'}, ensure_ascii=False)}\n\n")
        await asyncio.sleep(0.5)
        
        # 2. 模拟逐字生成回答
        response_text = "这是一个模拟的 AI 回答。Sanic 的流式接口可以让客户端实时接收数据，提供更好的用户体验。"
        
        for char in response_text:
            chunk = {
                "type": "content",
                "content": char,
            }
            await response.write(f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n")
            await asyncio.sleep(0.05)  # 模拟逐字生成延迟
        
        # 3. 发送完成标记
        await response.write(f"data: {json.dumps({'type': 'done', 'content': '完成'}, ensure_ascii=False)}\n\n")
        await response.write("data: [DONE]\n\n")
    
    return StreamingHTTPResponse(
        generate_chat_stream,
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


# ============================================================
# 混合接口演示（异步 + 流式）
# ============================================================

@bp.get("/stream/progress")
async def stream_progress(request):
    """
    进度流演示
    
    - 模拟长时间任务的进度推送
    - 客户端可以实时显示进度条
    - 适用于文件上传、数据处理等场景
    """
    # 从查询参数获取配置
    steps = int(request.args.get("steps", 5))
    delay = float(request.args.get("delay", 1.0))
    
    # 限制参数范围
    steps = max(1, min(20, steps))
    delay = max(0.1, min(5.0, delay))
    
    logger.info(f"开始进度流: steps={steps}, delay={delay}s")
    
    async def generate_progress_stream(response):
        """生成进度流"""
        for step in range(1, steps + 1):
            progress = {
                "type": "progress",
                "step": step,
                "total": steps,
                "percent": round(step / steps * 100, 1),
                "message": f"步骤 {step}/{steps} 完成",
                "timestamp": datetime.now().isoformat()
            }
            
            await response.write(f"data: {json.dumps(progress, ensure_ascii=False)}\n\n")
            
            # 模拟每个步骤的处理时间
            await asyncio.sleep(delay)
        
        # 完成
        await response.write(f"data: {json.dumps({'type': 'complete', 'message': '所有步骤完成'}, ensure_ascii=False)}\n\n")
        await response.write("data: [DONE]\n\n")
    
    return StreamingHTTPResponse(
        generate_progress_stream,
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )
