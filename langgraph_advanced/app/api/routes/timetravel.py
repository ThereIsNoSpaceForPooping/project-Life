# -*- coding: utf-8 -*-
"""
时间旅行路由

提供时间旅行功能的 API 接口：
- 获取执行历史
- 获取当前状态
- 修改历史状态
- 从历史状态重新执行
"""

from fastapi import APIRouter, HTTPException

from app.agent.advanced.time_travel import (
    time_travel_graph,
    get_execution_history,
    get_current_state,
    update_state_at_step,
    replay_from_step
)
from app.schemas.chat import TimeTravelRequest
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/timetravel/history/{conversation_id}")
async def get_history(conversation_id: str):
    """
    获取对话执行历史
    
    Args:
        conversation_id: 对话 ID
    
    Returns:
        dict: 执行历史列表
    """
    try:
        config = {"configurable": {"thread_id": conversation_id}}
        history = get_execution_history(config)
        
        return {
            "conversation_id": conversation_id,
            "history": history,
            "total_steps": len(history)
        }
    
    except Exception as e:
        logger.error(f"获取执行历史失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/timetravel/state/{conversation_id}")
async def get_state(conversation_id: str):
    """
    获取当前状态
    
    Args:
        conversation_id: 对话 ID
    
    Returns:
        dict: 当前状态信息
    """
    try:
        config = {"configurable": {"thread_id": conversation_id}}
        state = get_current_state(config)
        
        return {
            "conversation_id": conversation_id,
            "state": state
        }
    
    except Exception as e:
        logger.error(f"获取状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/timetravel/update")
async def update_state(request: TimeTravelRequest):
    """
    修改历史状态
    
    Args:
        request: 时间旅行请求（包含 conversation_id、step、new_values）
    
    Returns:
        dict: 更新后的状态
    """
    try:
        config = {"configurable": {"thread_id": request.conversation_id}}
        
        if not request.new_values:
            raise HTTPException(
                status_code=400,
                detail="new_values 不能为空"
            )
        
        # 确定要修改的节点
        as_node = f"step{request.step}" if request.step else "step1"
        
        # 更新状态
        updated_state = update_state_at_step(
            config,
            request.new_values,
            as_node=as_node
        )
        
        return {
            "conversation_id": request.conversation_id,
            "updated_state": updated_state,
            "message": f"状态已更新到 {as_node}"
        }
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"更新状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/timetravel/replay/{conversation_id}")
async def replay(conversation_id: str):
    """
    从当前状态重新执行
    
    Args:
        conversation_id: 对话 ID
    
    Returns:
        dict: 重新执行后的结果
    """
    try:
        config = {"configurable": {"thread_id": conversation_id}}
        
        # 从当前状态重新执行
        result = replay_from_step(config)
        
        return {
            "conversation_id": conversation_id,
            "result": result,
            "message": "重新执行完成"
        }
    
    except Exception as e:
        logger.error(f"重新执行失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
