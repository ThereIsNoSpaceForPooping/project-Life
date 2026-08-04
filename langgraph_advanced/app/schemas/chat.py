# -*- coding: utf-8 -*-
"""
数据模型定义

定义 API 请求和响应的数据模型。
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """对话请求"""
    message: str = Field(..., description="用户消息")
    conversation_id: str = Field(default="default", description="对话 ID")


class StepInfo(BaseModel):
    """步骤信息"""
    type: str = Field(..., description="步骤类型: agent_reasoning/tool_call/tool_result/final_answer")
    content: str = Field(default="", description="步骤内容")
    tool_name: Optional[str] = Field(None, description="工具名称（仅tool_call/tool_result类型）")
    tool_args: Optional[dict] = Field(None, description="工具参数（仅tool_call类型）")
    tool_result: Optional[str] = Field(None, description="工具结果（仅tool_result类型）")


class ChatResponse(BaseModel):
    """对话响应"""
    response: str = Field(..., description="AI 响应")
    conversation_id: str = Field(..., description="对话 ID")
    tool_calls: List[dict] = Field(default_factory=list, description="工具调用记录")
    steps: List[StepInfo] = Field(default_factory=list, description="推理步骤详情")


class StreamChunk(BaseModel):
    """流式响应块"""
    type: str = Field(..., description="块类型（content/tool_call/done）")
    content: str = Field(default="", description="内容")
    metadata: dict = Field(default_factory=dict, description="元数据")


class TaskRequest(BaseModel):
    """任务请求"""
    target_agent: str = Field(..., description="目标 Agent 名称")
    capability: str = Field(..., description="能力名称")
    input_data: dict = Field(default_factory=dict, description="输入数据")


class TaskResponse(BaseModel):
    """任务响应"""
    task_id: str = Field(..., description="任务 ID")
    status: str = Field(..., description="任务状态")
    result: Optional[dict] = Field(default=None, description="任务结果")


class MCPToolCallRequest(BaseModel):
    """MCP 工具调用请求"""
    tool_name: str = Field(..., description="工具名称")
    arguments: dict = Field(default_factory=dict, description="工具参数")


class MCPToolCallResponse(BaseModel):
    """MCP 工具调用响应"""
    result: str = Field(..., description="工具执行结果")
    is_error: bool = Field(default=False, description="是否错误")


class TimeTravelRequest(BaseModel):
    """时间旅行请求"""
    conversation_id: str = Field(..., description="对话 ID")
    step: Optional[int] = Field(default=None, description="目标步骤")
    new_values: Optional[dict] = Field(default=None, description="新的状态值")
