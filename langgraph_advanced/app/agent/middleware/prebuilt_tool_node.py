# -*- coding: utf-8 -*-
"""
Prebuilt-style ToolNode（自研兼容版）

背景
----
官方 `langgraph.prebuilt.ToolNode` 在当前环境存在依赖冲突：
    - langgraph==1.1.3 要求 langchain-core>=1.0 中的 `TOOL_MESSAGE_BLOCK_TYPES`
    - 当前安装的 langchain-core==0.3.63 缺少该符号，import 直接报 ImportError
为不阻塞业务，本模块提供一个"接口与官方一致、行为等价"的自研实现。

与官方 ToolNode 的对齐
----------------------
- 接收 `tools: Sequence[BaseTool]` 构造参数
- 节点函数签名 `__call__(state) -> dict`（向 messages 追加 ToolMessage）
- 支持 `handle_tool_errors=True/False/str/callable`
- 支持同步/异步工具（依据 tool.coroutine 是否存在）
- 工具名查找走 `tool.name`
- 工具执行出错时，将异常信息封装为 ToolMessage.content（不中断图）

差异（相对官方）
----------------
- 不支持 `InjectedState`/`InjectedStore`（本项目目前未用到）
- 不支持 `messages_key` 参数（写死 "messages"）
- 不执行 Send-style 路由分发
- 状态更新除了 messages 外，额外回写 `tool_call_count`

后续迁移
--------
当 langchain-core 升级到 >=1.0 后，可将本文件整体替换为：
    from langgraph.prebuilt import ToolNode
    tools_node = ToolNode(tools=tool_manager.get_all_tools(), handle_tool_errors=True)
    workflow.add_node("tools", tools_node)
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import traceback
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence, Union

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)


ErrorHandler = Union[bool, str, Callable[[Exception, Dict[str, Any]], str]]


class PrebuiltToolNode:
    """
    类官方 ToolNode 的工具执行节点。

    Usage:
        tool_node = PrebuiltToolNode(
            tools=tool_manager.get_all_tools(),
            handle_tool_errors=True,
        )
        workflow.add_node("tools", tool_node)
    """

    def __init__(
        self,
        tools: Sequence[BaseTool],
        *,
        handle_tool_errors: ErrorHandler = True,
        messages_key: str = "messages",
    ) -> None:
        """
        Args:
            tools: 可执行工具列表
            handle_tool_errors:
                - True  → 异常时把错误信息作为 ToolMessage.content 返回（推荐）
                - False → 异常直接抛出
                - str   → 用该字符串作为错误 content
                - callable → 自定义 (exc, tool_call) -> str
            messages_key: 状态中消息列表的字段名
        """
        # name -> tool 的查找表，避免每次遍历全列表
        self._tools_by_name: Dict[str, BaseTool] = {t.name: t for t in tools}
        self._all_tools: List[BaseTool] = list(tools)
        self._handle_tool_errors = handle_tool_errors
        self._messages_key = messages_key
        logger.info(
            "PrebuiltToolNode 初始化: %d 个工具 (%s)",
            len(self._all_tools),
            ", ".join(t.name for t in self._all_tools) or "无",
        )

    # ------------------------------------------------------------
    # 对外：作为 LangGraph 节点调用
    # ------------------------------------------------------------

    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """LangGraph 节点入口（async，以支持异步工具）"""
        logger.info(f"[PrebuiltToolNode] __call__ 被调用")
        messages = state.get(self._messages_key, [])
        if not messages:
            logger.warning("[PrebuiltToolNode] messages 为空，跳过")
            return {}

        last_ai = self._find_last_ai(messages)
        if last_ai is None:
            logger.warning("[PrebuiltToolNode] 找不到 AI 消息")
            return {}
        if not getattr(last_ai, "tool_calls", None):
            logger.warning("[PrebuiltToolNode] AI 消息没有 tool_calls")
            # DEBUG: 打印最后 3 条消息的类型和内容
            for i, msg in enumerate(messages[-3:]):
                msg_type = type(msg).__name__
                has_tc = hasattr(msg, 'tool_calls') and msg.tool_calls
                logger.warning(f"[PrebuiltToolNode-DEBUG] msg[{len(messages)-3+i}]: type={msg_type}, has_tool_calls={has_tc}, content={str(msg.content)[:80]}")
            return {}
        
        logger.info(f"[PrebuiltToolNode] 找到 {len(last_ai.tool_calls)} 个工具调用")

        # 并发执行所有 tool_calls（官方 ToolNode 也是并发）
        coros = [
            self._invoke_one(tc, state)
            for tc in last_ai.tool_calls
        ]
        tool_messages: List[ToolMessage] = await asyncio.gather(*coros)

        # 累加 tool_call_count（每次进入 tools 节点 +1，与项目原有语义一致）
        prev_count = int(state.get("tool_call_count", 0) or 0)

        return {
            self._messages_key: tool_messages,
            "tool_call_count": prev_count + 1,
        }

    # ------------------------------------------------------------
    # 内部：执行单个工具调用
    # ------------------------------------------------------------

    async def _invoke_one(
        self,
        tool_call: Dict[str, Any],
        state: Dict[str, Any],
    ) -> ToolMessage:
        """执行单个 tool_call 并返回 ToolMessage"""
        tool_name: str = tool_call.get("name", "")
        tool_args: Dict[str, Any] = tool_call.get("args", {}) or {}
        tool_call_id: str = tool_call.get("id", "")

        # 动态查找工具：优先从 tool_manager 获取（包含 MCP/A2A 工具），
        # 如果找不到再从初始化时的缓存中查找（本地工具）
        tool = self._tools_by_name.get(tool_name)
        if tool is None:
            # 尝试从 tool_manager 动态获取（解决 MCP/A2A 工具加载时序问题）
            try:
                from app.agent.shared.tool_manager import tool_manager
                all_tools = {t.name: t for t in tool_manager.get_all_tools()}
                tool = all_tools.get(tool_name)
                if tool:
                    logger.info(f"[PrebuiltToolNode] 动态加载工具: {tool_name}")
            except ImportError:
                logger.warning(f"无法导入 tool_manager，仅使用缓存工具")
        
        if tool is None:
            # 工具未找到：返回错误 ToolMessage，不抛异常
            content = f"工具 {tool_name!r} 未注册到 tool_manager，请检查 A2A/MCP 加载流程"
            logger.warning(content)
            return ToolMessage(content=content, name=tool_name, tool_call_id=tool_call_id)

        try:
            # 判断同步/异步：有 coroutine 属性即走异步
            if getattr(tool, "coroutine", None) is not None:
                result = await tool.ainvoke(tool_args)
            else:
                # 同步工具在线程池中执行，避免阻塞事件循环
                result = await asyncio.to_thread(tool.invoke, tool_args)

            content = result if isinstance(result, str) else str(result)
            # 日志限长
            preview = content if len(content) <= 200 else content[:200] + "..."
            logger.info("工具 %s 执行成功: %s", tool_name, preview)
            return ToolMessage(content=content, name=tool_name, tool_call_id=tool_call_id)

        except Exception as exc:  # noqa: BLE001
            err_content = self._format_error(exc, tool_call)
            logger.error("工具 %s 执行失败: %s", tool_name, exc, exc_info=True)
            return ToolMessage(content=err_content, name=tool_name, tool_call_id=tool_call_id)

    def _format_error(self, exc: Exception, tool_call: Dict[str, Any]) -> str:
        """根据 handle_tool_errors 策略格式化错误信息"""
        handler = self._handle_tool_errors
        if handler is False:
            raise exc
        if handler is True:
            return f"工具执行出错: {type(exc).__name__}: {exc}"
        if isinstance(handler, str):
            return handler
        if callable(handler):
            try:
                return handler(exc, tool_call)
            except Exception as inner:  # noqa: BLE001
                logger.error("自定义错误处理器失败: %s", inner)
                return f"工具执行出错: {exc}"
        return f"工具执行出错: {exc}"

    @staticmethod
    def _find_last_ai(messages: Sequence[Any]) -> Optional[AIMessage]:
        """从消息列表尾部查找最后一条 AIMessage"""
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                return msg
        return None


# ============================================================
# 路由函数：等价于官方 tools_condition
# ============================================================

def tools_condition(state: Dict[str, Any], messages_key: str = "messages") -> str:
    """
    类官方 tools_condition 的路由函数。

    输入：state
    输出：字符串
        - "tools"  → 最后一条 AI 消息包含 tool_calls，应进入工具执行
        - "__end__" → 没有 tool_calls，应结束（或交给调用方映射为 END）

    使用：
        workflow.add_conditional_edges(
            "agent",
            tools_condition,
            {"tools": "tools", "__end__": "reflection"},  # END 也可写作 END
        )
    """
    messages = state.get(messages_key, [])
    if not messages:
        return "__end__"
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            if getattr(msg, "tool_calls", None):
                return "tools"
            return "__end__"
    return "__end__"
