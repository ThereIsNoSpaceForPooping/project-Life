# -*- coding: utf-8 -*-
"""
A2A Server - 真实 A2A 协议实现

基于 Google A2A（Agent-to-Agent）规范 v0.2 实现，
完整的 JSON-RPC 2.0 端点 + SSE 流式 + 任务状态机。

协议规范：https://google-a2a.github.io/A2A/
核心能力：
    - AgentCard 服务发现（/.well-known/agent.json）
    - JSON-RPC 2.0 over HTTP POST (/a2a/jsonrpc)
    - Server-Sent Events 流式响应
    - 任务状态机：submitted → working → input-required → completed/failed/canceled
    - 多模态消息：TextPart / FilePart / DataPart
    - Push Notifications（webhook 异步通知）

支持的 JSON-RPC 方法：
    - message/send        发送消息（同步返回任务）
    - message/stream      发送消息（SSE 流式返回）
    - tasks/get           获取任务详情
    - tasks/cancel        取消任务
    - tasks/resubscribe   重新订阅任务事件

Agent 列表：
    - researcher    研究助手（信息搜索和整理）
    - coder         编码助手（代码生成和审查）
    - translator    翻译助手（多语言翻译）
    - analyzer      分析助手（数据分析和洞察）

运行：
    python main.py
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional

# ============================================================
# 路径与环境
# ============================================================
BASE_DIR: Path = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv

load_dotenv(BASE_DIR / ".env")

# ============================================================
# 日志配置
# ============================================================
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)-7s | %(name)-20s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger: logging.Logger = logging.getLogger("a2a_server")

# ============================================================
# Web 框架
# ============================================================
# 使用 Starlette（轻量、async-native）实现 A2A 协议
# 相比 FastAPI，Starlette 更接近 ASGI 原生，更适合协议层服务
try:
    from starlette.applications import Starlette
    from starlette.middleware.cors import CORSMiddleware
    from starlette.requests import Request
    from starlette.responses import JSONResponse, Response
    from starlette.routing import Route
    import uvicorn
except ImportError as exc:  # pragma: no cover
    logger.error(
        "缺少依赖: %s\n请执行: pip install starlette uvicorn",
        exc,
    )
    raise SystemExit(1) from exc

# 业务模块
from config import Config
from agents.registry import agent_registry

# A2A 协议层
from protocol.types import (
    AgentCard,
    AgentCapabilities,
    AgentSkill,
    TaskState,
    TaskStatus,
    Message,
    Part,
    TextPart,
    DataPart,
    FilePart,
    JSONRPCRequest,
    JSONRPCResponse,
    JSONRPCError,
    SendMessageRequest,
    SendMessageResponse,
    StreamResponse,
    Task,
    Artifact,
    parse_parts,
)
from protocol.task_manager import TaskManager
from protocol.executor import TaskExecutor
from protocol.streaming import EventBroker


# ============================================================
# 全局实例
# ============================================================
task_manager: TaskManager = TaskManager()
event_broker: EventBroker = EventBroker()
executor: TaskExecutor = TaskExecutor(
    task_manager=task_manager,
    event_broker=event_broker,
    agent_registry=agent_registry,
)


# ============================================================
# 辅助：构造 JSON-RPC 错误
# ============================================================
JSON_RPC_PARSE_ERROR: int = -32700
JSON_RPC_INVALID_REQUEST: int = -32600
JSON_RPC_METHOD_NOT_FOUND: int = -32601
JSON_RPC_INVALID_PARAMS: int = -32602
JSON_RPC_INTERNAL_ERROR: int = -32603


# ============================================================
# 业务 Agent 卡片（服务发现）
# ============================================================
def build_agent_card() -> Dict[str, Any]:
    """
    构造 A2A Agent Card

    Agent Card 是 A2A 规范要求的服务发现机制。
    客户端通过 GET /.well-known/agent.json 获取服务信息。

    Returns:
        符合 A2A 规范的 Agent Card 字典
    """
    skills: List[Dict[str, Any]] = []
    for skill in agent_registry.get_all_skills():
        skills.append(
            {
                "id": skill["id"],
                "name": skill["name"],
                "description": skill["description"],
                "tags": skill.get("tags", []),
                "examples": skill.get("examples", []),
                "inputModes": skill.get("inputModes", ["text"]),
                "outputModes": skill.get("outputModes", ["text"]),
            }
        )

    return {
        "name": os.getenv("A2A_AGENT_NAME", "project-life-a2a"),
        "description": (
            "Project-Life A2A Server - 提供 4 个专业化 Agent："
            "researcher（研究）、coder（编程）、translator（翻译）、analyzer（分析）"
        ),
        "url": f"http://{Config.HOST}:{Config.PORT}",
        "version": "1.0.0",
        "protocolVersion": "0.2.5",
        "capabilities": {
            "streaming": True,              # 支持 SSE 流式响应
            "pushNotifications": False,     # 不启用 webhook
            "stateTransitionHistory": True, # 任务状态历史可查
        },
        "defaultInputModes": ["text"],
        "defaultOutputModes": ["text"],
        "skills": skills,
        "provider": {
            "organization": "Project-Life",
            "url": "https://github.com/project-life",
        },
    }


# ============================================================
# 路由处理
# ============================================================
async def health_handler(_request: Request) -> JSONResponse:
    """
    GET /health - 健康检查（非 A2A 协议）
    """
    return JSONResponse(
        {
            "status": "ok",
            "service": "a2a_server",
            "protocol": "A2A",
            "version": "0.2.5",
            "agents": len(agent_registry.list_agents()),
            "tasks": task_manager.size(),
        }
    )


async def agent_card_handler(_request: Request) -> JSONResponse:
    """
    GET /.well-known/agent.json - A2A 服务发现端点

    符合 A2A 规范：客户端必须先访问此端点获取 Agent Card。
    """
    return JSONResponse(build_agent_card())


async def jsonrpc_handler(request: Request) -> Response:
    """
    POST /a2a/jsonrpc - A2A 主端点（JSON-RPC 2.0）

    支持方法：
        - message/send       同步发送消息
        - message/stream     流式发送消息（返回 SSE）
        - tasks/get          获取任务状态
        - tasks/cancel       取消任务
        - tasks/resubscribe  重新订阅任务事件

    错误码：
        -32700 Parse error      JSON 解析失败
        -32600 Invalid request  请求格式错误
        -32601 Method not found 未知方法
        -32602 Invalid params   参数校验失败
        -32603 Internal error   内部错误
    """
    # 1. 解析 JSON-RPC 请求
    try:
        raw: bytes = await request.body()
        body: Dict[str, Any] = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        return _error_response(
            None,
            JSON_RPC_PARSE_ERROR,
            f"JSON 解析失败: {exc}",
        )
    except Exception as exc:  # pragma: no cover
        return _error_response(
            None,
            JSON_RPC_PARSE_ERROR,
            f"请求体读取失败: {exc}",
        )

    # 2. 校验 JSON-RPC 结构
    if not isinstance(body, dict):
        return _error_response(
            None,
            JSON_RPC_INVALID_REQUEST,
            "请求必须是 JSON 对象",
        )

    jsonrpc: str = body.get("jsonrpc", "")
    method: str = body.get("method", "")
    req_id: Any = body.get("id")
    params: Dict[str, Any] = body.get("params", {})

    if jsonrpc != "2.0":
        return _error_response(
            req_id,
            JSON_RPC_INVALID_REQUEST,
            f"jsonrpc 必须是 '2.0'，实际: {jsonrpc!r}",
        )

    logger.info("[JSON-RPC] method=%s, id=%s", method, req_id)

    # 3. 路由到具体方法
    try:
        if method == "message/send":
            return await _handle_message_send(req_id, params)
        elif method == "message/stream":
            return await _handle_message_stream(req_id, params)
        elif method == "tasks/get":
            return await _handle_tasks_get(req_id, params)
        elif method == "tasks/cancel":
            return await _handle_tasks_cancel(req_id, params)
        elif method == "tasks/resubscribe":
            return await _handle_tasks_resubscribe(req_id, params)
        else:
            return _error_response(
                req_id,
                JSON_RPC_METHOD_NOT_FOUND,
                f"未知方法: {method}",
            )
    except Exception as exc:  # pragma: no cover
        logger.exception("[JSON-RPC] 内部错误: %s", exc)
        return _error_response(
            req_id,
            JSON_RPC_INTERNAL_ERROR,
            f"内部错误: {exc}",
        )


def _error_response(
    req_id: Any,
    code: int,
    message: str,
    data: Any = None,
) -> JSONResponse:
    """
    构造 JSON-RPC 错误响应
    """
    error: Dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return JSONResponse({"jsonrpc": "2.0", "id": req_id, "error": error})


# ============================================================
# JSON-RPC 方法实现
# ============================================================
async def _handle_message_send(
    req_id: Any,
    params: Dict[str, Any],
) -> JSONResponse:
    """
    message/send - 同步发送消息

    请求参数：
        {
            "message": {
                "role": "user",
                "parts": [{"type": "text", "text": "..."}]
            },
            "agentName": "researcher"   # 可选，指定目标 Agent
        }

    响应：
        {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "task": {
                    "id": "...",
                    "state": "completed",
                    "messages": [...],
                    "artifacts": [...]
                }
            }
        }
    """
    # 参数校验
    if "message" not in params:
        return _error_response(
            req_id, JSON_RPC_INVALID_PARAMS, "缺少 message 字段"
        )

    message: Dict[str, Any] = params["message"]
    if not isinstance(message, dict) or "parts" not in message:
        return _error_response(
            req_id, JSON_RPC_INVALID_PARAMS, "message 必须是对象且包含 parts"
        )

    parts: List[Dict[str, Any]] = message.get("parts", [])
    user_text: str = _extract_text_from_parts(parts)
    agent_name: str = params.get("agentName", "")

    # 选择 Agent
    target_agent: str = agent_name or _infer_agent_from_text(user_text)
    if not agent_registry.has_agent(target_agent):
        # 尝试用第一个可用 Agent
        available: List[str] = agent_registry.list_agent_names()
        if not available:
            return _error_response(
                req_id,
                JSON_RPC_INTERNAL_ERROR,
                "没有可用的 Agent",
            )
        target_agent = available[0]
        logger.warning(
            "[message/send] 指定的 Agent '%s' 不存在，使用 '%s'",
            agent_name, target_agent,
        )

    # 创建任务
    task: Task = task_manager.create_task(
        agent_name=target_agent,
        input_text=user_text,
        input_parts=parts,
    )

    # 同步执行
    await executor.execute(task, user_text)

    # 返回最终任务状态
    final_task: Task = task_manager.get_task(task.id)
    return JSONResponse(
        {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"task": final_task.to_dict()},
        }
    )


async def _handle_message_stream(
    req_id: Any,
    params: Dict[str, Any],
) -> Response:
    """
    message/stream - 流式发送消息（SSE）

    返回 Server-Sent Events 流，事件类型：
        - status    任务状态变更
        - message   中间消息（如思考过程）
        - artifact  产物（最终结果）
        - end       流结束
    """
    if "message" not in params:
        return _error_response(
            req_id, JSON_RPC_INVALID_PARAMS, "缺少 message 字段"
        )

    message: Dict[str, Any] = params["message"]
    parts: List[Dict[str, Any]] = message.get("parts", [])
    user_text: str = _extract_text_from_parts(parts)
    agent_name: str = params.get("agentName", "")

    target_agent: str = agent_name or _infer_agent_from_text(user_text)
    if not agent_registry.has_agent(target_agent):
        available: List[str] = agent_registry.list_agent_names()
        if not available:
            return _error_response(
                req_id, JSON_RPC_INTERNAL_ERROR, "没有可用的 Agent"
            )
        target_agent = available[0]

    # 创建任务并订阅
    task: Task = task_manager.create_task(
        agent_name=target_agent,
        input_text=user_text,
        input_parts=parts,
    )
    subscriber_id: str = f"sub_{uuid.uuid4().hex[:8]}"
    event_broker.subscribe(task.id, subscriber_id)

    async def event_generator() -> AsyncIterator[bytes]:
        """
        SSE 事件生成器

        协议格式：
            event: status
            data: {"state": "working", ...}

            event: artifact
            data: {...}

            event: end
            data: {"taskId": "..."}
        """
        try:
            # 异步执行任务
            exec_task: asyncio.Task = asyncio.create_task(
                executor.execute(task, user_text)
            )

            # 流式推送事件
            while True:
                event: Optional[Dict[str, Any]] = await event_broker.get_event(
                    task.id, subscriber_id, timeout=0.5
                )
                if event is None:
                    if exec_task.done():
                        # 拉取剩余事件
                        while True:
                            tail: Optional[Dict[str, Any]] = (
                                await event_broker.get_event(
                                    task.id, subscriber_id, timeout=0.0
                                )
                            )
                            if tail is None:
                                break
                            yield _sse_format(tail)
                        break
                    continue

                yield _sse_format(event)

                if event.get("type") == "end":
                    break

            # 等待执行完成
            await exec_task
        finally:
            event_broker.unsubscribe(task.id, subscriber_id)

    return Response(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _handle_tasks_get(
    req_id: Any,
    params: Dict[str, Any],
) -> JSONResponse:
    """
    tasks/get - 获取任务详情
    """
    task_id: str = params.get("id", "")
    if not task_id:
        return _error_response(req_id, JSON_RPC_INVALID_PARAMS, "缺少 id 字段")

    task: Optional[Task] = task_manager.get_task(task_id)
    if task is None:
        return _error_response(
            req_id, JSON_RPC_INVALID_PARAMS, f"任务不存在: {task_id}"
        )

    return JSONResponse(
        {"jsonrpc": "2.0", "id": req_id, "result": {"task": task.to_dict()}}
    )


async def _handle_tasks_cancel(
    req_id: Any,
    params: Dict[str, Any],
) -> JSONResponse:
    """
    tasks/cancel - 取消任务
    """
    task_id: str = params.get("id", "")
    if not task_id:
        return _error_response(req_id, JSON_RPC_INVALID_PARAMS, "缺少 id 字段")

    task: Optional[Task] = task_manager.get_task(task_id)
    if task is None:
        return _error_response(
            req_id, JSON_RPC_INVALID_PARAMS, f"任务不存在: {task_id}"
        )

    success: bool = task_manager.cancel_task(task_id)
    if not success:
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "task": task.to_dict(),
                    "canceled": False,
                    "reason": "任务已完成或已取消",
                },
            }
        )

    event_broker.publish(
        task_id, {"type": "status", "state": "canceled", "taskId": task_id}
    )
    event_broker.publish(task_id, {"type": "end", "taskId": task_id})

    updated: Task = task_manager.get_task(task_id)
    return JSONResponse(
        {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"task": updated.to_dict(), "canceled": True},
        }
    )


async def _handle_tasks_resubscribe(
    req_id: Any,
    params: Dict[str, Any],
) -> Response:
    """
    tasks/resubscribe - 重新订阅任务事件流
    """
    task_id: str = params.get("id", "")
    if not task_id:
        return _error_response(req_id, JSON_RPC_INVALID_PARAMS, "缺少 id 字段")

    task: Optional[Task] = task_manager.get_task(task_id)
    if task is None:
        return _error_response(
            req_id, JSON_RPC_INVALID_PARAMS, f"任务不存在: {task_id}"
        )

    subscriber_id: str = f"sub_{uuid.uuid4().hex[:8]}"
    event_broker.subscribe(task_id, subscriber_id)

    async def replay() -> AsyncIterator[bytes]:
        try:
            # 发送当前状态
            yield _sse_format(
                {
                    "type": "status",
                    "state": task.state.value,
                    "taskId": task_id,
                }
            )

            if task.is_terminal():
                yield _sse_format({"type": "end", "taskId": task_id})
                return

            # 订阅新事件
            while True:
                event: Optional[Dict[str, Any]] = await event_broker.get_event(
                    task_id, subscriber_id, timeout=0.5
                )
                if event is None:
                    # 检查任务是否已终止
                    latest: Optional[Task] = task_manager.get_task(task_id)
                    if latest and latest.is_terminal():
                        yield _sse_format(
                            {"type": "end", "taskId": task_id}
                        )
                        break
                    continue

                yield _sse_format(event)

                if event.get("type") == "end":
                    break
        finally:
            event_broker.unsubscribe(task_id, subscriber_id)

    return Response(
        replay(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


# ============================================================
# 辅助函数
# ============================================================
def _extract_text_from_parts(parts: List[Dict[str, Any]]) -> str:
    """
    从多模态 Parts 中提取纯文本

    Args:
        parts: A2A 消息 parts 列表

    Returns:
        拼接后的纯文本
    """
    texts: List[str] = []
    for part in parts:
        if part.get("type") == "text":
            texts.append(part.get("text", ""))
        elif part.get("type") == "data":
            # DataPart 序列化为 JSON
            data: Any = part.get("data")
            if isinstance(data, (dict, list)):
                texts.append(json.dumps(data, ensure_ascii=False))
    return "\n".join(texts).strip()


def _infer_agent_from_text(text: str) -> str:
    """
    根据用户文本推断目标 Agent

    简单的关键词路由，生产环境建议使用 LLM 路由。

    Args:
        text: 用户文本

    Returns:
        Agent 名称
    """
    text_lower: str = text.lower()
    if any(kw in text_lower for kw in ("翻译", "translate", "英译", "中译", "译成")):
        return "translator"
    if any(kw in text_lower for kw in ("代码", "code", "函数", "python", "实现")):
        return "coder"
    if any(kw in text_lower for kw in ("分析", "analyze", "数据", "趋势", "统计")):
        return "analyzer"
    # 默认 researcher
    return "researcher"


def _sse_format(event: Dict[str, Any]) -> bytes:
    """
    将事件格式化为 SSE 协议字节串

    SSE 协议格式：
        event: <type>
        data: <json>

    Args:
        event: 事件字典

    Returns:
        编码后的字节串
    """
    event_type: str = event.get("type", "message")
    data_str: str = json.dumps(event, ensure_ascii=False, default=str)
    return f"event: {event_type}\ndata: {data_str}\n\n".encode("utf-8")


# ============================================================
# 应用构造
# ============================================================
def create_app() -> Starlette:
    """
    构造 A2A Server Starlette 应用

    路由：
        GET  /health                  健康检查
        GET  /.well-known/agent.json  A2A 服务发现（Agent Card）
        POST /a2a/jsonrpc             JSON-RPC 2.0 主端点
    """
    routes: List[Route] = [
        Route("/health", agent_card_handler, methods=["GET"]),
        Route("/.well-known/agent.json", agent_card_handler, methods=["GET"]),
        Route("/a2a/jsonrpc", jsonrpc_handler, methods=["POST"]),
    ]

    app: Starlette = Starlette(
        debug=False,
        routes=routes,
    )

    # CORS（允许跨域调试）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app


app: Starlette = create_app()


# ============================================================
# 启动入口
# ============================================================
def _print_banner() -> None:
    """打印启动横幅"""
    agents: List[str] = agent_registry.list_agent_names()
    print(
        f"""
╔═══════════════════════════════════════════════════════════╗
║          A2A Server (Google A2A 协议 v0.2)               ║
╠═══════════════════════════════════════════════════════════╣
║  监听地址: http://{Config.HOST}:{Config.PORT:<30}║
║  Agent 数量: {len(agents):<43}║
║                                                           ║
║  可用 Agent:                                              ║
║   • researcher    研究助手（信息搜索和整理）               ║
║   • coder         编码助手（代码生成和审查）               ║
║   • translator    翻译助手（多语言翻译）                   ║
║   • analyzer      分析助手（数据分析和洞察）               ║
╠═══════════════════════════════════════════════════════════╣
║  端点:                                                    ║
║   GET  /.well-known/agent.json  Agent Card 发现            ║
║   POST /a2a/jsonrpc             JSON-RPC 2.0 主端点        ║
║   GET  /health                  健康检查                   ║
╠═══════════════════════════════════════════════════════════╣
║  支持的 JSON-RPC 方法:                                    ║
║   • message/send       同步发送消息                       ║
║   • message/stream     流式发送消息（SSE）                 ║
║   • tasks/get          获取任务详情                        ║
║   • tasks/cancel       取消任务                            ║
║   • tasks/resubscribe  重新订阅任务事件                    ║
╚═══════════════════════════════════════════════════════════╝
"""
    )


def main() -> None:
    """主入口"""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="A2A Server - 真实 Google A2A 协议实现"
    )
    parser.add_argument("--host", default=Config.HOST, help="监听地址")
    parser.add_argument("--port", type=int, default=Config.PORT, help="监听端口")
    args: argparse.Namespace = parser.parse_args()

    _print_banner()
    logger.info("[启动] A2A Server 监听: http://%s:%d", args.host, args.port)

    uvicorn.run(
        "main:app",
        host=args.host,
        port=args.port,
        log_level="info",
        access_log=True,
    )


if __name__ == "__main__":
    main()
