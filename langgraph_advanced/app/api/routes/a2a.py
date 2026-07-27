# -*- coding: utf-8 -*-
"""
A2A 路由

提供 A2A（Agent-to-Agent）功能的 API 接口：
- 发现 Agent
- 创建任务
- 查询任务状态
- 获取消息历史
"""

from fastapi import APIRouter, HTTPException

from app.agent.a2a import a2a_protocol, agent_card_registry, task_manager, message_history
from app.schemas.chat import TaskRequest, TaskResponse
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/a2a/agents")
async def list_agents():
    """
    列出所有可用 Agent
    
    Returns:
        dict: Agent 列表
    """
    try:
        agents = a2a_protocol.discover_agents()
        
        return {
            "agents": [
                {
                    "name": agent.name,
                    "description": agent.description,
                    "version": agent.version,
                    "endpoint": agent.endpoint,
                    "capabilities": [
                        {
                            "name": cap.name,
                            "description": cap.description
                        }
                        for cap in agent.capabilities
                    ]
                }
                for agent in agents
            ]
        }
    
    except Exception as e:
        logger.error(f"列出 Agent 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/a2a/agents/{agent_name}")
async def get_agent(agent_name: str):
    """
    获取指定 Agent 的详细信息
    
    Args:
        agent_name: Agent 名称
    
    Returns:
        dict: Agent 详细信息
    """
    try:
        agent = a2a_protocol.get_agent_card(agent_name)
        if not agent:
            raise HTTPException(
                status_code=404,
                detail=f"Agent '{agent_name}' 不存在"
            )
        
        return agent.to_dict()
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"获取 Agent 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/a2a/tasks", response_model=TaskResponse)
async def create_task(request: TaskRequest):
    """
    创建 A2A 任务
    
    Args:
        request: 任务请求（包含 target_agent、capability、input_data）
    
    Returns:
        TaskResponse: 任务响应
    """
    try:
        logger.info(f"创建 A2A 任务: {request.target_agent}.{request.capability}")
        
        # 创建任务
        task = a2a_protocol.create_task(
            target_agent=request.target_agent,
            capability=request.capability,
            input_data=request.input_data
        )
        
        # 执行任务
        task = await a2a_protocol.execute_task(task.id)
        
        return TaskResponse(
            task_id=task.id,
            status=task.status.value,
            result=task.output_data if task.status.value == "completed" else None
        )
    
    except Exception as e:
        logger.error(f"创建任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/a2a/tasks/{task_id}")
async def get_task_status(task_id: str):
    """
    查询任务状态
    
    Args:
        task_id: 任务 ID
    
    Returns:
        dict: 任务状态信息
    """
    try:
        status = a2a_protocol.get_task_status(task_id)
        if not status:
            raise HTTPException(
                status_code=404,
                detail=f"任务 '{task_id}' 不存在"
            )
        
        return status
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"查询任务状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/a2a/tasks")
async def list_tasks(limit: int = 100):
    """
    列出所有任务
    
    Args:
        limit: 最大返回数量
    
    Returns:
        dict: 任务列表
    """
    try:
        tasks = task_manager.list_tasks(limit=limit)
        
        return {
            "tasks": [task.to_dict() for task in tasks]
        }
    
    except Exception as e:
        logger.error(f"列出任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/a2a/messages")
async def get_messages(
    from_agent: str = None,
    to_agent: str = None,
    task_id: str = None,
    limit: int = 100
):
    """
    获取消息历史
    
    Args:
        from_agent: 按发送者过滤
        to_agent: 按接收者过滤
        task_id: 按任务 ID 过滤
        limit: 最大返回数量
    
    Returns:
        dict: 消息列表
    """
    try:
        messages = a2a_protocol.get_message_history(
            from_agent=from_agent,
            to_agent=to_agent,
            task_id=task_id
        )
        
        return {
            "messages": messages[:limit]
        }
    
    except Exception as e:
        logger.error(f"获取消息历史失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
