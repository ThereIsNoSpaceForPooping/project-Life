# -*- coding: utf-8 -*-
"""
对话相关数据模型

定义智能体对话的请求和响应结构
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class Message(BaseModel):
    """消息模型"""
    role: Literal["user", "assistant", "system"] = Field(..., description="消息角色")
    content: str = Field(..., description="消息内容")


class ChatRequest(BaseModel):
    """对话请求模型"""
    messages: List[Message] = Field(..., description="对话消息列表")
    provider: Optional[str] = Field("minimax", description="LLM 提供商: minimax/dashscope")
    model: Optional[str] = Field(None, description="模型名称，不指定则使用默认模型")
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0, description="温度参数")
    max_tokens: Optional[int] = Field(2000, ge=1, le=8000, description="最大生成 token 数")
    enable_tools: Optional[bool] = Field(True, description="是否启用工具")


class ChatResponse(BaseModel):
    """对话响应模型（阻塞接口）"""
    content: str = Field(..., description="AI 回复内容")
    tool_calls: Optional[List[dict]] = Field(None, description="工具调用记录")
    usage: Optional[dict] = Field(None, description="Token 使用情况")
    finish_reason: str = Field("complete", description="结束原因")


class StreamChunk(BaseModel):
    """流式响应数据块模型"""
    type: Literal["thinking", "tool_call", "tool_result", "content", "done"] = Field(
        ..., description="数据块类型"
    )
    content: Optional[str] = Field(None, description="数据块内容")
    metadata: Optional[dict] = Field(None, description="元数据")
