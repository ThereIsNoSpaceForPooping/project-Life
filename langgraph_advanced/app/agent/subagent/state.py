# -*- coding: utf-8 -*-
"""
Subagent 子图（Supervisor 模式）—— 状态定义

本模块定义 Supervisor-Worker 模式子图所使用的 State。

设计说明：
    - 状态独立于 MasterState，通过 subagent_node 的入口/出口映射与主图解耦。
    - messages 使用 lambda 拼接，避免引入 add_messages 的"按 ID 去重"语义
      （Supervisor 节点会重复 push AIMessage，去重会导致 worker 输出被吞）。
    - worker_outputs 是有序列表，记录每次 worker 调用的输出。
    - iteration 计数器由 Supervisor 自增，到达 max_iterations 强制结束，
      防止 Supervisor 在"无法判断 FINISH"时无限循环。

字段约定：
    - messages       : 子图内部消息历史（顺序追加）
    - query          : 原始用户任务（入口由 subagent_node 注入）
    - next_worker    : Supervisor 写入的下一跳 worker 名称
    - worker_outputs : 历次 worker 的输出累积（汇总节点读取）
    - subagent_result: 子图出口结果（finalize_node 写入）
    - iteration      : Supervisor 循环计数
    - max_iterations : 循环上限（默认 5）
"""

from typing import Annotated, List, Optional

from langchain_core.messages import BaseMessage
from typing_extensions import TypedDict


class SubagentState(TypedDict):
    """
    Subagent 子图状态（Supervisor 模式）

    Attributes:
        messages: 子图内部消息历史（顺序追加，不去重）。
        query: 入口注入的用户原始任务。
        next_worker: Supervisor 决策的下一跳 worker（researcher/coder/analyst/FINISH）。
        worker_outputs: 历次 worker 输出的有序列表。
        subagent_result: 子图最终结果（供主图读取）。
        iteration: Supervisor 循环计数（防止死循环）。
        max_iterations: Supervisor 循环上限。
    """

    # ------------------------------------------------------------------
    # 消息历史：使用 lambda 顺序追加（不去重）
    # ------------------------------------------------------------------
    # 说明：Supervisor 节点会重复推送 AIMessage（如"决定调用 researcher"），
    #       若使用 add_messages 会按 ID 去重，导致后续 worker 输出被吞。
    messages: Annotated[List[BaseMessage], lambda x, y: x + y]

    # ------------------------------------------------------------------
    # 入口注入的用户任务
    # ------------------------------------------------------------------
    query: str

    # ------------------------------------------------------------------
    # Supervisor 决策的下一跳 worker
    # ------------------------------------------------------------------
    next_worker: Optional[str]

    # ------------------------------------------------------------------
    # 历次 worker 输出的有序列表
    # ------------------------------------------------------------------
    worker_outputs: List[str]

    # ------------------------------------------------------------------
    # 子图出口结果（由 finalize_node 写入，供主图 subagent_node 读取）
    # ------------------------------------------------------------------
    subagent_result: Optional[str]

    # ------------------------------------------------------------------
    # 循环控制字段
    # ------------------------------------------------------------------
    iteration: int
    max_iterations: int
