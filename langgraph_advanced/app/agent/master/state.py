# -*- coding: utf-8 -*-
"""
统一大图状态定义

MasterState 包含所有功能模块所需的字段，支持完整任务链路。
"""

from typing import List, Optional, Dict, Any, Annotated
from typing_extensions import TypedDict
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


# ============================================================
# 结构化输出模型
# ============================================================

class TaskAnalysis(BaseModel):
    """任务分析结果（路由器使用）"""
    task_type: str = Field(..., description="任务类型：simple/search/document/complex/unknown")
    priority: str = Field(..., description="优先级：high/medium/low")
    complexity: int = Field(..., ge=1, le=10, description="复杂度 1-10")
    description: str = Field(..., description="任务描述")
    requires_tools: bool = Field(default=False, description="是否需要工具")


class ReflectionResult(BaseModel):
    """自我反思结果"""
    is_satisfactory: bool = Field(..., description="是否满意")
    confidence: float = Field(..., ge=0, le=1, description="置信度")
    issues: List[str] = Field(default_factory=list, description="发现的问题")
    suggestions: str = Field(default="", description="改进建议")


# ============================================================
# 统一状态定义
# ============================================================

class MasterState(TypedDict):
    """
    统一大图状态

    包含所有功能模块所需的字段，支持完整任务链路。
    """
    # 消息历史（LangGraph 自动追加）
    messages: Annotated[List[BaseMessage], add_messages]

    # 基础信息
    query: str                          # 用户原始输入
    conversation_id: str                # 对话ID

    # 安全护栏
    input_safe: bool                    # 输入是否安全
    output_safe: bool                   # 输出是否安全
    guard_warnings: List[str]           # 安全警告

    # 路由决策
    task_analysis: Optional[dict]       # 任务分析结果
    next_route: Optional[str]           # 下一个路由

    # 子图结果
    research_result: Optional[str]      # 研究结果
    research_sources: List[str]         # 研究来源

    # Map-Reduce 结果（仅保留被其他节点读取的字段）
    final_summary: Optional[str]        # Map-Reduce 最终摘要（agent_node / summarizer 读取）

    # Subagent 子图结果（Supervisor 模式）
    subagent_result: Optional[str]      # subagent 节点输出（agent_node / summarizer 读取）

    # 人机协作
    pending_action: Optional[str]       # 待确认操作
    human_feedback: Optional[str]       # 人工反馈
    approved: bool                      # 是否批准

    # 自我反思
    reflection: Optional[dict]          # 反思结果
    retry_count: int                    # 重试次数
    max_retries: int                    # 最大重试次数

    # 工具调用控制
    tool_call_count: int                # 工具调用次数（防止死循环）
    max_tool_calls: int                 # 最大工具调用次数

    # 重复调用守卫（防抖）—— 详见 app.agent.middleware.stuck_guard
    stuck_signature: Optional[str]      # 最近一次工具调用的稳定签名
    stuck_count: int                    # 连续相同签名的累计次数
    _force_skip_tools: bool             # 内部标记：stuck_guard 判定后是否强制跳过 tools 节点

    # 强制工具路由（v3 —— 关键词触发）
    # 说明：router_node 检测到特定关键词时强制注入目标工具名，
    #       agent_node 读取后追加"必须调用该工具"的 SystemMessage，避免
    #       LLM 自行判断"翻译是简单任务"而跳过工具调用。
    force_tool: Optional[str]           # router 注入：强制 agent 调用的工具名（如 a2a_translator）

    # 最终输出
    final_response: Optional[str]       # 最终响应
