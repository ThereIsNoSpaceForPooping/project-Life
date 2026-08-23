# -*- coding: utf-8 -*-
"""
A2A 路由（代理到独立 a2a_server/）

本路由不再本地实现 A2A 协议，而是作为代理转发到 a2a_server/ 进程
（8002 端口），遵循 Google A2A 规范 v0.2。这样保持了架构清晰：

    langgraph_advanced → A2AClient → 独立 a2a_server
    （8005）            （httpx）    （8002）

提供接口：
- GET    /a2a/agents               列出所有 Agent（从 Agent Card 提取）
- GET    /a2a/agents/{name}        Agent 详情
- POST   /a2a/tasks                同步创建并执行任务（message/send）
- GET    /a2a/tasks/{id}           查询任务状态（tasks/get）
- POST   /a2a/tasks/{id}/cancel    取消任务（tasks/cancel）
- POST   /a2a/tasks/stream         流式执行任务（message/stream，SSE 输出）
- GET    /a2a/server/info          a2a_server 元信息

调用策略：
    1) 优先复用本进程内已加载的 a2a_loader.client（零开销）
    2) 否则通过 httpx 直接调用 a2a_server 的 JSON-RPC 端点
"""

import json
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.agent.a2a.tools_loader import a2a_loader
from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.chat import (
    A2ATaskCancelResponse,
    A2ATaskRequest,
    A2ATaskResponse,
    A2ATaskStatusResponse,
)

logger: logging.Logger = get_logger(__name__)

# 创建路由实例（无 prefix，由 main_app 统一挂载）
router: APIRouter = APIRouter()


# ============================================================
# 辅助：获取独立 a2a_server 的根 URL
# ============================================================
def _a2a_base_url() -> str:
    """
    获取独立 a2a_server 的根 URL

    优先从 settings 读取，便于在生产环境通过环境变量切换。
    """
    return getattr(settings, "A2A_SERVER_URL", "http://localhost:8002").rstrip("/")


def _is_local_client_ready() -> bool:
    """
    检查本进程内的 A2A Client 是否已连接

    Returns:
        bool: 已连接返回 True
    """
    return (
        a2a_loader is not None
        and a2a_loader.client is not None
    )


# ============================================================
# 辅助：HTTP 调用 a2a_server
# ============================================================
async def _http_get_agent_card() -> Dict[str, Any]:
    """
    通过 HTTP 拉取 a2a_server 的 Agent Card

    符合 A2A 规范：GET /.well-known/agent.json

    Returns:
        Agent Card 字典
    """
    url: str = f"{_a2a_base_url()}/.well-known/agent.json"
    async with httpx.AsyncClient(timeout=10.0) as client:
        response: httpx.Response = await client.get(url)
        response.raise_for_status()
        return response.json()


async def _http_jsonrpc(method: str, params: Dict[str, Any], timeout: float = 60.0) -> Dict[str, Any]:
    """
    通过 HTTP 调用 a2a_server 的 JSON-RPC 端点

    Args:
        method: JSON-RPC 方法名
        params: 参数
        timeout: 超时秒数

    Returns:
        响应 result 字典

    Raises:
        HTTPException: 调用失败
    """
    url: str = f"{_a2a_base_url()}/a2a/jsonrpc"
    payload: Dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params,
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        response: httpx.Response = await client.post(url, json=payload)
        response.raise_for_status()
        body: Dict[str, Any] = response.json()

    # JSON-RPC 错误处理
    if "error" in body:
        error: Dict[str, Any] = body["error"]
        raise HTTPException(
            status_code=502,
            detail=f"A2A Server 错误 [{error.get('code')}]: {error.get('message')}",
        )
    return body.get("result", {})


def _extract_agent_names(agent_card: Dict[str, Any]) -> List[str]:
    """
    从 Agent Card 中提取唯一的 Agent 名称列表

    A2A Server 把每个 Agent 的每个 skill 注册为一条 skill 记录，
    命名约定：`<agent_name>-<skill_index>` 或纯 `<agent_name>`。

    Args:
        agent_card: Agent Card 字典

    Returns:
        Agent 名称列表（保序去重）
    """
    seen: set = set()
    ordered: List[str] = []
    for skill in agent_card.get("skills", []):
        skill_id: str = skill.get("id", "")
        agent_name: str = skill_id.split("-")[0] if "-" in skill_id else skill_id
        if agent_name and agent_name not in seen:
            seen.add(agent_name)
            ordered.append(agent_name)
    return ordered


def _extract_agent_skills(agent_card: Dict[str, Any], agent_name: str) -> List[Dict[str, Any]]:
    """
    从 Agent Card 中提取指定 Agent 的所有 skill

    Args:
        agent_card: Agent Card 字典
        agent_name: Agent 名称

    Returns:
        skill 列表
    """
    return [
        skill for skill in agent_card.get("skills", [])
        if (skill.get("id", "").split("-")[0] if "-" in skill.get("id", "") else skill.get("id", "")) == agent_name
    ]


def _agent_card_to_summary(agent_card: Dict[str, Any]) -> Dict[str, Any]:
    """
    从 Agent Card 构造简化的 agent 摘要信息

    Args:
        agent_card: Agent Card 字典

    Returns:
        摘要字典（含 name/description/version/skills_summary）
    """
    return {
        "name": agent_card.get("name", ""),
        "description": agent_card.get("description", ""),
        "version": agent_card.get("version", ""),
        "protocolVersion": agent_card.get("protocolVersion", ""),
        "url": agent_card.get("url", ""),
        "capabilities": agent_card.get("capabilities", {}),
        "defaultInputModes": agent_card.get("defaultInputModes", []),
        "defaultOutputModes": agent_card.get("defaultOutputModes", []),
        "provider": agent_card.get("provider", {}),
    }


# ============================================================
# Agent 列表 & 详情
# ============================================================
@router.get("/a2a/agents")
async def list_a2a_agents() -> Dict[str, Any]:
    """
    列出所有可用的 A2A Agent

    数据源：a2a_server 的 Agent Card（/.well-known/agent.json）
    每个 Agent 在 Card 中以若干 skill 形式注册。

    Returns:
        dict: Agent 列表 + Server 摘要
    """
    try:
        # 1) 优先使用本进程内已加载的 client
        if _is_local_client_ready() and a2a_loader.client.agent_card is None:
            await a2a_loader.client.discover()

        if _is_local_client_ready() and a2a_loader.client.agent_card:
            agent_card: Dict[str, Any] = a2a_loader.client.agent_card
        else:
            # 2) HTTP fallback
            agent_card = await _http_get_agent_card()

        # 提取 Agent 列表
        agent_names: List[str] = _extract_agent_names(agent_card)
        agents: List[Dict[str, Any]] = []
        for name in agent_names:
            skills: List[Dict[str, Any]] = _extract_agent_skills(agent_card, name)
            agents.append(
                {
                    "name": name,
                    "description": (
                        f"Remote A2A Agent '{name}' with {len(skills)} skill(s)"
                    ),
                    "endpoint": _a2a_base_url(),
                    "skills": [
                        {
                            "id": s.get("id"),
                            "name": s.get("name"),
                            "description": s.get("description"),
                            "tags": s.get("tags", []),
                            "examples": s.get("examples", []),
                        }
                        for s in skills
                    ],
                }
            )

        return {
            "server": _agent_card_to_summary(agent_card),
            "agents": agents,
            "total": len(agents),
        }
    except httpx.HTTPError as exc:
        logger.error("调用 a2a_server 失败: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"A2A Server 不可达: {exc}",
        ) from exc
    except Exception as exc:
        logger.error("列出 A2A Agent 失败: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/a2a/agents/{agent_name}")
async def get_a2a_agent(agent_name: str) -> Dict[str, Any]:
    """
    获取指定 A2A Agent 的详细信息

    Args:
        agent_name: Agent 名称

    Returns:
        dict: Agent 详情（含 skills）
    """
    try:
        # 拉取 Agent Card
        if _is_local_client_ready() and a2a_loader.client.agent_card:
            agent_card: Dict[str, Any] = a2a_loader.client.agent_card
        else:
            agent_card = await _http_get_agent_card()

        skills: List[Dict[str, Any]] = _extract_agent_skills(agent_card, agent_name)
        if not skills:
            raise HTTPException(
                status_code=404,
                detail=f"Agent '{agent_name}' 不存在或未注册 skill",
            )

        return {
            "name": agent_name,
            "description": (
                f"Remote A2A Agent '{agent_name}' with {len(skills)} skill(s)"
            ),
            "endpoint": _a2a_base_url(),
            "skills": skills,
        }
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        logger.error("调用 a2a_server 失败: %s", exc)
        raise HTTPException(
            status_code=502, detail=f"A2A Server 不可达: {exc}"
        ) from exc
    except Exception as exc:
        logger.error("获取 A2A Agent 失败: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ============================================================
# 任务执行（同步）
# ============================================================
@router.post("/a2a/tasks", response_model=A2ATaskResponse)
async def create_a2a_task(request: A2ATaskRequest) -> A2ATaskResponse:
    """
    创建并同步执行 A2A 任务

    对应 A2A 协议 JSON-RPC 方法 `message/send`。
    调用方在 body 中指定目标 Agent 与任务文本，Server 端同步执行后
    返回包含 messages 和 artifacts 的完整 Task。

    Args:
        request: A2A 任务请求

    Returns:
        A2ATaskResponse: 任务执行结果
    """
    try:
        logger.info(
            "[routes/a2a] 转发任务: agent=%s, text='%s...'",
            request.agent_name, request.text[:40],
        )

        if _is_local_client_ready():
            # 1) 走 SDK 风格（直接调用 a2a_loader.client）
            task: Dict[str, Any] = await a2a_loader.client.send(
                text=request.text,
                agent_name=request.agent_name,
                session_id=request.session_id,
            )
        else:
            # 2) HTTP fallback 到 a2a_server
            params: Dict[str, Any] = {
                "message": {
                    "role": "user",
                    "parts": [{"type": "text", "text": request.text}],
                },
                "agentName": request.agent_name,
            }
            if request.session_id:
                params["sessionId"] = request.session_id

            result: Dict[str, Any] = await _http_jsonrpc("message/send", params)
            task = result.get("task", {})

        return A2ATaskResponse(
            task_id=task.get("id", ""),
            state=task.get("state") or task.get("status", {}).get("state", "unknown"),
            messages=task.get("messages", []) or task.get("history", []),
            artifacts=task.get("artifacts", []),
            error=task.get("error"),
        )
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        logger.error("调用 a2a_server 失败: %s", exc)
        raise HTTPException(
            status_code=502, detail=f"A2A Server 不可达: {exc}"
        ) from exc
    except Exception as exc:
        logger.error("A2A 任务执行失败: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ============================================================
# 任务状态查询
# ============================================================
@router.get("/a2a/tasks/{task_id}", response_model=A2ATaskStatusResponse)
async def get_a2a_task(task_id: str) -> A2ATaskStatusResponse:
    """
    查询 A2A 任务状态

    对应 A2A 协议 JSON-RPC 方法 `tasks/get`。

    Args:
        task_id: 任务 ID

    Returns:
        A2ATaskStatusResponse: 任务状态详情
    """
    try:
        if _is_local_client_ready():
            task: Dict[str, Any] = await a2a_loader.client.get_task(task_id)
        else:
            result: Dict[str, Any] = await _http_jsonrpc("tasks/get", {"id": task_id})
            task = result.get("task", {})

        if not task:
            raise HTTPException(
                status_code=404, detail=f"任务 '{task_id}' 不存在"
            )

        return A2ATaskStatusResponse(
            task_id=task.get("id", task_id),
            state=task.get("state") or task.get("status", {}).get("state", "unknown"),
            agent_name=task.get("agentName", "") or task.get("agent_name", ""),
            messages=task.get("messages", []) or task.get("history", []),
            artifacts=task.get("artifacts", []),
            status=task.get("status", {"state": task.get("state", "unknown")}),
        )
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        logger.error("调用 a2a_server 失败: %s", exc)
        raise HTTPException(
            status_code=502, detail=f"A2A Server 不可达: {exc}"
        ) from exc
    except Exception as exc:
        logger.error("查询 A2A 任务失败: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ============================================================
# 任务取消
# ============================================================
@router.post("/a2a/tasks/{task_id}/cancel", response_model=A2ATaskCancelResponse)
async def cancel_a2a_task(task_id: str) -> A2ATaskCancelResponse:
    """
    取消 A2A 任务

    对应 A2A 协议 JSON-RPC 方法 `tasks/cancel`。

    Args:
        task_id: 任务 ID

    Returns:
        A2ATaskCancelResponse: 取消结果
    """
    try:
        if _is_local_client_ready():
            result: Dict[str, Any] = await a2a_loader.client.cancel_task(task_id)
        else:
            result = await _http_jsonrpc("tasks/cancel", {"id": task_id})

        task: Dict[str, Any] = result.get("task", {})
        return A2ATaskCancelResponse(
            task_id=task.get("id", task_id),
            canceled=bool(result.get("canceled", True)),
            state=task.get("state", "unknown"),
            reason=result.get("reason"),
        )
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        logger.error("调用 a2a_server 失败: %s", exc)
        raise HTTPException(
            status_code=502, detail=f"A2A Server 不可达: {exc}"
        ) from exc
    except Exception as exc:
        logger.error("取消 A2A 任务失败: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ============================================================
# 任务流式执行（SSE）
# ============================================================
@router.post("/a2a/tasks/stream")
async def stream_a2a_task(request: A2ATaskRequest) -> StreamingResponse:
    """
    流式执行 A2A 任务（SSE）

    对应 A2A 协议 JSON-RPC 方法 `message/stream`。
    a2a_server 会以 SSE 推送 status/message/artifact/end 等事件，
    本路由作为透传代理，将事件原样转发给前端。

    Args:
        request: A2A 任务请求

    Returns:
        StreamingResponse: text/event-stream
    """
    async def event_proxy() -> AsyncIterator[bytes]:
        """
        内部异步生成器：将 a2a_server 的 SSE 事件原样转发

        协议格式（每条事件）：
            event: <type>
            data: <json>

        两条事件之间以空行分隔。
        """
        params: Dict[str, Any] = {
            "message": {
                "role": "user",
                "parts": [{"type": "text", "text": request.text}],
            },
            "agentName": request.agent_name,
        }
        if request.session_id:
            params["sessionId"] = request.session_id

        url: str = f"{_a2a_base_url()}/a2a/jsonrpc"
        payload: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "message/stream",
            "params": params,
        }

        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("POST", url, json=payload) as response:
                    if response.status_code != 200:
                        err_text: str = await response.aread()
                        err_payload: Dict[str, Any] = {
                            "type": "error",
                            "code": response.status_code,
                            "message": err_text.decode("utf-8", errors="ignore"),
                        }
                        yield (
                            f"event: error\n"
                            f"data: {json.dumps(err_payload, ensure_ascii=False)}\n\n"
                        ).encode("utf-8")
                        return

                    # 原样转发 SSE 流
                    async for line in response.aiter_lines():
                        # SSE 协议以空行分隔事件，原样透传
                        yield (line + "\n").encode("utf-8")
        except httpx.HTTPError as exc:
            logger.error("SSE 流转发失败: %s", exc)
            err_payload: Dict[str, Any] = {
                "type": "error",
                "code": 502,
                "message": f"A2A Server 不可达: {exc}",
            }
            yield (
                f"event: error\n"
                f"data: {json.dumps(err_payload, ensure_ascii=False)}\n\n"
            ).encode("utf-8")
        except Exception as exc:
            logger.error("SSE 流异常: %s", exc)
            err_payload: Dict[str, Any] = {
                "type": "error",
                "code": 500,
                "message": str(exc),
            }
            yield (
                f"event: error\n"
                f"data: {json.dumps(err_payload, ensure_ascii=False)}\n\n"
            ).encode("utf-8")

    return StreamingResponse(
        event_proxy(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲
            "Connection": "keep-alive",
        },
    )


# ============================================================
# Server 元信息
# ============================================================
@router.get("/a2a/server/info")
async def get_a2a_server_info() -> Dict[str, Any]:
    """
    获取 a2a_server 的元信息

    用于运维监控和健康检查。

    Returns:
        dict: Server 信息（含可达性、协议版本等）
    """
    info: Dict[str, Any] = {
        "name": "project-life-a2a",
        "version": "1.0.0",
        "protocol": "A2A",
        "protocol_version": "0.2.5",
        "url": _a2a_base_url(),
        "transport": "jsonrpc-over-http + sse",
        "loaded_locally": _is_local_client_ready(),
    }

    # 尝试健康检查
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response: httpx.Response = await client.get(f"{_a2a_base_url()}/health")
            if response.status_code == 200:
                info["health"] = response.json()
                info["reachable"] = True
            else:
                info["reachable"] = False
                info["health_error"] = f"HTTP {response.status_code}"
    except httpx.HTTPError as exc:
        info["reachable"] = False
        info["health_error"] = str(exc)

    return info
