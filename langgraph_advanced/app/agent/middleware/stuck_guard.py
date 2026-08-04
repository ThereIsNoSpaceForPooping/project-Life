# -*- coding: utf-8 -*-
"""
Stuck Guard —— 重复工具调用检测（防抖节点）

设计目标
--------
解决 LLM Agent 在多轮工具调用中陷入"反复调用同一工具+同一参数"的死循环。
例如：
    调用 a2a_translator(query="翻译：黄瓜")  → 拿到结果
    调用 a2a_translator(query="翻译：黄瓜")  → 拿到结果
    调用 a2a_translator(query="翻译：黄瓜")  → 拿到结果  ← 无意义的循环

工作原理
--------
1. 计算最近一次 AIMessage 的"工具调用签名"：
       sig = "tool_name:json(args)"（按 (name, args) 排序，保证稳定）
2. 与 state 中保存的"上一次签名"对比：
       - 相同 → stuck_count += 1
       - 不同 → stuck_count 重置为 1
3. 当 stuck_count >= threshold（默认 2）：
       - 在 messages 末尾追加一条 SystemMessage 提示 LLM 收尾
       - 标记 `_force_skip_tools = True`，路由层据此跳到 reflection

签名稳定性
----------
为避免 LLM 偶发地把 args 写成 `{"query": "翻译：黄瓜"}` vs `{"query":"翻译：黄瓜"}`
（空格差异）导致误判，对 args 做：
- 按 key 排序
- 跳过 None 值
- ensure_ascii=False 保证中文一致

边界条件
--------
- AIMessage 没有 tool_calls → 透传，不写入签名
- 多个 tool_calls 混合 → 用全部分类签名拼成一个总签名
- threshold <= 0 → 关闭检测（恒透传）
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Iterable, List, Optional, Sequence

from langchain_core.messages import AIMessage, SystemMessage, ToolCall

logger = logging.getLogger(__name__)


# ============================================================
# 签名计算
# ============================================================

def _normalize_args(args: Any) -> Any:
    """
    规范化工具调用参数：dict 按 key 排序后序列化；其他类型直接 str。

    说明：
    - 这是为了防止 JSON 序列化顺序差异导致签名误判
    - 不做值归一化（大小写等）—— 业务语义可能依赖大小写
    """
    if isinstance(args, dict):
        return {k: _normalize_args(v) for k, v in sorted(args.items())}
    if isinstance(args, (list, tuple)):
        return [_normalize_args(x) for x in args]
    return args


def compute_tool_call_signature(tool_calls: Sequence[Dict[str, Any]]) -> str:
    """
    计算一组工具调用的稳定签名。

    Args:
        tool_calls: AIMessage.tool_calls 列表（每个元素含 id/name/args）

    Returns:
        形如 "a2a_translator:{\"query\":\"翻译：黄瓜\"}|get_time:{}" 的字符串
        （不包含 tool_call.id，因为 LangChain 每次会生成新 id，会破坏签名稳定性）
    """
    parts: List[str] = []
    # 关键：按 (name, args) 排序，绝不能用 tool_call.id
    # 原因：LangChain 每次 LLM 响应都会生成新的 tool_call_id，
    #       会让签名每次都不同，stuck_guard 永远检测不到重复。
    sorted_calls = sorted(
        tool_calls,
        key=lambda tc: (tc.get("name", ""), json.dumps(_normalize_args(tc.get("args", {})), ensure_ascii=False, sort_keys=True, default=str)),
    )
    for tc in sorted_calls:
        name = tc.get("name", "")
        normalized_args = _normalize_args(tc.get("args", {}))
        try:
            # ensure_ascii=False 保证中文 args 的签名稳定
            args_json = json.dumps(normalized_args, ensure_ascii=False, sort_keys=True, default=str)
        except (TypeError, ValueError) as exc:
            # 极端情况：用 repr 兜底
            logger.warning("工具参数 JSON 序列化失败，使用 repr 兜底: %s", exc)
            args_json = repr(normalized_args)
        parts.append(f"{name}:{args_json}")
    return "|".join(parts)


# ============================================================
# 节点函数
# ============================================================

# 默认阈值：连续 2 次完全相同即拦截
DEFAULT_STUCK_THRESHOLD = 2


def stuck_guard_node(
    state: Dict[str, Any],
    *,
    threshold: int = DEFAULT_STUCK_THRESHOLD,
    messages_key: str = "messages",
) -> Dict[str, Any]:
    """
    Stuck Guard 节点函数。

    检测"最近一次 AIMessage 的工具调用签名"是否与上一次相同，
    若连续相同达到 threshold 次，则：
    1. 追加一条 SystemMessage 提示 LLM 收尾
    2. 写入 `_force_skip_tools=True` 让路由跳到 reflection

    Args:
        state: LangGraph 状态字典（必须含 messages）
        threshold: 连续相同签名的最大次数；<=0 关闭检测
        messages_key: 状态中消息列表的字段名

    Returns:
        状态更新字典（永远不抛异常，确保流程不被中断）
    """
    # 关闭检测：直接透传
    if threshold <= 0:
        return {}

    messages = state.get(messages_key, [])
    if not messages:
        return {}

    # 取最后一条 AIMessage
    last_ai: Optional[AIMessage] = None
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            last_ai = msg
            break

    # 没有 AI 消息，或没有 tool_calls：透传
    if last_ai is None or not getattr(last_ai, "tool_calls", None):
        # 同时重置计数器，避免历史脏数据干扰
        return {
            "stuck_signature": None,
            "stuck_count": 0,
            "_force_skip_tools": False,
        }

    tool_calls: List[ToolCall] = last_ai.tool_calls
    current_sig = compute_tool_call_signature(tool_calls)
    prev_sig = state.get("stuck_signature")
    prev_count = int(state.get("stuck_count", 0) or 0)

    # 签名不同：重置计数
    if current_sig != prev_sig:
        logger.info(
            "stuck_guard: 签名变化, 重置计数 (prev=%s, new=%s)",
            prev_sig, current_sig,
        )
        return {
            "stuck_signature": current_sig,
            "stuck_count": 1,
            "_force_skip_tools": False,
        }

    # 签名相同：累加
    new_count = prev_count + 1
    force_skip = new_count >= threshold

    if force_skip:
        logger.warning(
            "stuck_guard: 连续 %d 次相同工具调用签名, 强制跳过 tools "
            "(sig=%s, threshold=%d)",
            new_count, current_sig, threshold,
        )
        # 提示 LLM 收尾（追加到 messages）
        hint = SystemMessage(
            content=(
                "系统提示：检测到连续多次调用相同工具且参数一致。"
                "请基于已有工具结果直接回答用户，不要再次调用同一工具。"
                f"（当前签名: {current_sig[:120]}）"
            )
        )
        return {
            "stuck_signature": current_sig,
            "stuck_count": new_count,
            "_force_skip_tools": True,
            messages_key: [hint],
        }

    # 还在阈值内：仅累加，不打断流程
    return {
        "stuck_signature": current_sig,
        "stuck_count": new_count,
        "_force_skip_tools": False,
    }


# ============================================================
# 路由辅助
# ============================================================

def route_after_stuck_guard(state: Dict[str, Any]) -> str:
    """
    stuck_guard 之后的路由决策。

    返回值约定（与 master_graph 中 add_conditional_edges 的 mapping 对齐）：
        - "human_review"：正常进入人工审核节点
        - "reflection"  ：强制跳过工具，直接进入反思
    """
    if state.get("_force_skip_tools"):
        return "reflection"
    return "human_review"


# ============================================================
# 自检（仅在直接执行本文件时运行）
# ============================================================

if __name__ == "__main__":
    # 简单单测：相同签名连续 2 次应触发 force_skip
    s1 = compute_tool_call_signature([
        {"id": "1", "name": "a2a_translator", "args": {"query": "翻译：黄瓜"}}
    ])
    s2 = compute_tool_call_signature([
        {"id": "1", "name": "a2a_translator", "args": {"query": "翻译：黄瓜"}}
    ])
    s3 = compute_tool_call_signature([
        {"id": "1", "name": "a2a_translator", "args": {"query": "翻译：苹果"}}
    ])
    assert s1 == s2, f"相同调用应得到相同签名: {s1} vs {s2}"
    assert s1 != s3, f"参数不同应得到不同签名: {s1} vs {s3}"
    print("签名稳定性 OK")
    print("  sig1:", s1)
    print("  sig3:", s3)
