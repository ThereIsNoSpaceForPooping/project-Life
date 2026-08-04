# -*- coding: utf-8 -*-
"""
A2A 工具动态加载器

启动时从 A2A Server 获取所有可用 Agent，
将每个 Agent 包装为 LangChain StructuredTool，
使 Agent 能够像使用本地工具一样调用 A2A Agent。

架构：
    启动 → /a2a/agents → 包装为 StructuredTool → 合并到 TOOLS
    Agent → bind_tools(本地工具 + MCP工具 + A2A工具) → LLM 自主选择调用
    tool_node → 本地工具直接执行 / MCP 工具走 HTTP / A2A 工具走 HTTP
"""

import json
from typing import Any, Dict, List

from langchain_core.tools import StructuredTool
from pydantic import create_model

from app.agent.a2a.simple_client import a2a_client
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


# ============================================================
# A2A 工具名称前缀
# ============================================================
A2A_TOOL_PREFIX = "a2a_"


def is_a2a_tool(tool_name: str) -> bool:
    """
    判断是否为 A2A 工具（通过名称前缀判断）

    Args:
        tool_name: 工具名称

    Returns:
        是否为 A2A 工具
    """
    return tool_name.startswith(A2A_TOOL_PREFIX)


def a2a_original_name(tool_name: str) -> str:
    """
    获取 A2A Agent 在 A2A Server 上的原始名称（去掉前缀）

    Args:
        tool_name: 带前缀的工具名称（如 a2a_researcher）

    Returns:
        原始名称（如 researcher）
    """
    return tool_name[len(A2A_TOOL_PREFIX):]


# ============================================================
# A2A Agent 输入字段映射表
# ============================================================
# 背景：A2A Server 上每个 Agent 的 input_data 字段约定不同：
#   - translator : 必填 text
#   - coder      : 必填 requirement
#   - analyzer   : 必填 data
#   - researcher : 必填 query
# 旧版硬编码 {"query": query} 只对 researcher 生效，其他 agent 都会拿到空字符串
# 修复：按 agent_name 映射到正确的字段名，query 作为额外上下文追加
A2A_INPUT_FIELD_MAP: dict[str, str] = {
    "translator": "text",
    "coder":      "requirement",
    "analyzer":   "data",
    "researcher": "query",
}


def _build_a2a_input(agent_name: str, query: str) -> dict:
    """
    按 agent_name 构造符合 A2A Server 约定的 input_data 字典。

    Args:
        agent_name: Agent 名称（已去掉 a2a_ 前缀）
        query: 用户查询内容

    Returns:
        符合 A2A Server 约定的 input_data
    """
    field = A2A_INPUT_FIELD_MAP.get(agent_name, "query")
    payload: dict = {field: query}
    # 透传：把 query 也作为 fallback 附在 payload 里
    # 避免某些 agent 内部同时校验两个字段
    if field != "query":
        payload["query"] = query
    return payload


# ============================================================
# A2A Agent 调用执行器
# ============================================================

async def _execute_a2a_agent(agent_name: str, query: str) -> str:
    """
    执行 A2A Agent 调用（异步）

    通过 HTTP 请求将任务发送到 A2A Server 执行。

    Args:
        agent_name: Agent 名称（已去掉 a2a_ 前缀）
        query: 用户查询内容

    Returns:
        Agent 执行结果（JSON 字符串）
    """
    logger.info(f"执行 A2A Agent: {agent_name}, 查询: {query[:100]}")

    # 按 agent_name 构造正确的 input_data（关键修复）
    input_data = _build_a2a_input(agent_name, query)

    try:
        result = await a2a_client.create_task(
            agent_name=agent_name,
            input_data=input_data
        )

        # 将结果序列化为字符串
        if isinstance(result, dict) and "error" in result:
            error_msg = f"A2A Agent {agent_name} 执行失败: {result['error']}"
            logger.error(error_msg)
            return json.dumps({"error": result["error"]}, ensure_ascii=False)

        result_str = json.dumps(result, ensure_ascii=False, default=str)
        logger.info(f"A2A Agent {agent_name} 执行成功")
        logger.info(f"A2A Agent {agent_name} 返回结果: {result_str}")
        return result_str

    except Exception as e:
        error_msg = f"A2A Agent {agent_name} 调用异常: {e}"
        logger.error(error_msg)
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ============================================================
# 动态加载器
# ============================================================

async def load_a2a_tools() -> List[StructuredTool]:
    """
    从 A2A Server 动态加载所有 Agent 并包装为 LangChain StructuredTool

    流程：
    1. 检查 A2A Server 是否健康
    2. 调用 /a2a/agents 获取 Agent 列表
    3. 为每个 Agent 动态生成 Pydantic 模型 + 包装函数
    4. 返回 StructuredTool 列表

    Returns:
        LangChain StructuredTool 列表（工具名带 a2a_ 前缀）
    """
    logger.info("=" * 50)
    logger.info("开始加载 A2A 工具")
    logger.info(f"A2A Server 地址: {settings.A2A_SERVER_URL}")

    # 1. 健康检查
    try:
        healthy = await a2a_client.health_check()
        if not healthy:
            logger.warning("A2A Server 不可用，跳过动态加载")
            return []
    except Exception as e:
        logger.warning(f"A2A Server 健康检查失败: {e}，跳过动态加载")
        return []

    # 2. 获取 Agent 列表
    try:
        a2a_agent_list = await a2a_client.list_agents()
    except Exception as e:
        logger.warning(f"获取 A2A Agent 列表失败: {e}，跳过动态加载")
        return []

    if not a2a_agent_list:
        logger.info("A2A Server 未注册任何 Agent")
        return []

    # 3. 逐个包装为 StructuredTool
    langchain_tools: List[StructuredTool] = []

    for agent_info in a2a_agent_list:
        original_name = agent_info["name"]
        wrapped_name = f"{A2A_TOOL_PREFIX}{original_name}"
        description = agent_info.get("description", "无描述")
        capabilities = agent_info.get("capabilities", [])

        try:
            # 动态生成 Pydantic 参数模型（统一使用 query 参数）
            input_schema = create_model(
                f"A2A_{original_name.replace('-', '_').title().replace('_', '')}_Schema",
                query=(str, ...)  # 必填参数：用户查询
            )

            # 创建异步调用函数（使用默认参数绑定避免闭包问题）
            async def call_fn(query: str, _name=original_name):
                return await _execute_a2a_agent(_name, query)

            # 包装为 StructuredTool
            # ============================================================
            # 防死循环描述（v2）：在 description 中显式提醒 LLM "用完即止"
            # 现象：a2a_translator / a2a_researcher 等"一次性"工具被反复调用
            # 策略：description 中追加一次性 + 不重试 + 拿到结果即收尾的引导
            # ============================================================
            base_desc = f"{description}（能力: {', '.join(capabilities) if capabilities else '通用'}）"
            one_shot_hint = (
                "【使用注意】这是一个一次性工具：仅在用户首次明确需要该能力时调用一次，"
                "拿到结果后请直接基于结果回答用户，"
                "不要在后续轮次再次调用同一工具，除非用户明确要求。"
            )
            # ============================================================
            # v3：翻译类工具的【强制】前缀
            # ============================================================
            # 作用：与 router 关键词 + agent SystemMessage 形成"三层强制"：
            #   1. router 关键词触发 → 注入 force_tool
            #   2. agent 追加 SystemMessage 显式要求
            #   3. 工具自身 description 标注【强制】
            # 即使 LLM 忽略了前两层，也能在工具描述中看到【强制】而调用
            force_prefix = ""
            if original_name == "translator":
                force_prefix = (
                    "【强制·翻译专用】凡是用户提到『翻译/translate/译成』，"
                    "无论任务看起来多简单，都必须调用本工具完成翻译。"
                    "禁止用自身知识直接翻译。\n"
                )
            final_desc = f"{force_prefix}{base_desc}\n{one_shot_hint}"

            structured_tool = StructuredTool(
                name=wrapped_name,
                description=final_desc,
                func=None,  # 仅使用异步
                coroutine=call_fn,
                args_schema=input_schema,
            )

            langchain_tools.append(structured_tool)
            logger.info(f"  [A2A] {wrapped_name} ← {description[:40]}")

        except Exception as e:
            logger.warning(f"  [A2A] {original_name} 包装失败: {e}，跳过")

    logger.info(f"A2A 工具加载完成: 成功 {len(langchain_tools)}/{len(a2a_agent_list)} 个")
    logger.info("=" * 50)

    return langchain_tools
