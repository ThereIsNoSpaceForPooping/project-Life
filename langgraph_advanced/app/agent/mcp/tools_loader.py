# -*- coding: utf-8 -*-
"""
MCP 工具动态加载器

启动时从 MCP Server 获取所有可用工具，
将每个 MCP 工具包装为 LangChain StructuredTool，
使 Agent 能够像使用本地工具一样调用 MCP 工具。

架构：
    启动 → /mcp/tools/list → 包装为 StructuredTool → 合并到 TOOLS
    Agent → bind_tools(本地工具 + MCP工具) → LLM 自主选择调用
    tool_node → 本地工具直接执行 / MCP 工具走 HTTP
"""

import json
from typing import Any, Dict, List, Optional

from langchain_core.tools import StructuredTool
from pydantic import create_model

from app.agent.mcp.simple_client import mcp_client
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


# ============================================================
# MCP 工具名称前缀
# ============================================================
MCP_TOOL_PREFIX = "mcp_"


def is_mcp_tool(tool_name: str) -> bool:
    """
    判断是否为 MCP 工具（通过名称前缀判断）

    Args:
        tool_name: 工具名称

    Returns:
        是否为 MCP 工具
    """
    return tool_name.startswith(MCP_TOOL_PREFIX)


def mcp_original_name(tool_name: str) -> str:
    """
    获取 MCP 工具在 MCP Server 上的原始名称（去掉前缀）

    Args:
        tool_name: 带前缀的工具名称（如 mcp_http_get）

    Returns:
        原始名称（如 http_get）
    """
    return tool_name[len(MCP_TOOL_PREFIX):]


# ============================================================
# JSON Schema 类型映射
# ============================================================

# JSON Schema 类型 → Python 类型
_TYPE_MAP = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
}


def _json_schema_to_pydantic_model(
    tool_name: str,
    parameters: Dict[str, Any]
) -> type:
    """
    将 JSON Schema 参数定义转换为 Pydantic 模型

    Args:
        tool_name: 工具名称（用于模型命名）
        parameters: JSON Schema 格式的参数定义

    Returns:
        动态生成的 Pydantic 模型类

    示例:
        输入:
            {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}
        输出:
            一个包含 url: str 字段的 Pydantic 模型
    """
    properties = parameters.get("properties", {})
    required = parameters.get("required", [])

    # 构建 Pydantic 字段定义
    field_definitions: Dict[str, Any] = {}
    for prop_name, prop_schema in properties.items():
        # 获取 Python 类型（未知类型默认为 str）
        json_type = prop_schema.get("type", "string")
        python_type = _TYPE_MAP.get(json_type, str)

        # 获取字段描述和默认值
        description = prop_schema.get("description", "")
        default_value = prop_schema.get("default", None)

        # 必填字段无默认值，可选字段默认为 None
        if prop_name in required:
            field_definitions[prop_name] = (python_type, ...)
        else:
            field_definitions[prop_name] = (Optional[python_type], default_value)

    # 动态创建 Pydantic 模型
    model_name = f"MCP_{tool_name.replace('-', '_').title().replace('_', '')}_Schema"
    return create_model(model_name, **field_definitions)


# ============================================================
# MCP 工具调用执行器
# ============================================================

async def _execute_mcp_tool(tool_name: str, arguments: Dict[str, Any]) -> str:
    """
    执行 MCP 工具调用（异步）

    通过 HTTP 请求将工具调用发送到 MCP Server 执行。

    Args:
        tool_name: 工具名称（已去掉 mcp_ 前缀）
        arguments: 工具参数

    Returns:
        工具执行结果（JSON 字符串）
    """
    logger.info(f"执行 MCP 工具: {tool_name}, 参数: {arguments}")

    try:
        result = await mcp_client.call_tool(tool_name, arguments)

        # 将结果序列化为字符串
        if isinstance(result, dict) and "error" in result:
            error_msg = f"MCP 工具 {tool_name} 执行失败: {result['error']}"
            logger.error(error_msg)
            return json.dumps({"error": result["error"]}, ensure_ascii=False)

        result_str = json.dumps(result, ensure_ascii=False, default=str)
        logger.info(f"MCP 工具 {tool_name} 执行成功")
        logger.info(f"MCP 工具 {tool_name} 返回结果: {result_str}")
        return result_str

    except Exception as e:
        error_msg = f"MCP 工具 {tool_name} 调用异常: {e}"
        logger.error(error_msg)
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ============================================================
# 动态加载器
# ============================================================

# ============================================================
# MCP 工具描述前缀映射（v4 新增）
# ============================================================
# 目的：给每个 MCP 工具的 description 加上【必用·XX专用】前缀，
#       引导 LLM 在看到对应类型任务时优先调用本工具。
# 配合：master_graph.py 的 FORCE_TOOL_KEYWORDS 关键词路由
# 效果：三层防护 - 关键词路由 + SystemMessage 强制 + 工具描述引导
MCP_TOOL_DESC_PREFIX_MAP: dict[str, str] = {
    # 文件操作
    "file_read":    "【必用·文件读取专用】",
    "file_write":   "【必用·文件写入专用】",
    "file_list":    "【必用·目录列表专用】",
    "file_delete":  "【必用·文件删除专用】",
    # 数据库操作
    "db_query":     "【必用·SQL查询专用 SELECT】",
    "db_execute":   "【必用·SQL执行专用 INSERT/UPDATE/DELETE】",
    "db_tables":    "【必用·数据库表列表专用】",
    "db_schema":    "【必用·表结构查询专用】",
    # HTTP 请求
    "http_request": "【必用·HTTP通用请求专用】",
    "http_get":     "【必用·HTTP GET 专用】",
    "http_post":    "【必用·HTTP POST 专用】",
    # 代码执行
    "code_execute":  "【必用·Python代码执行专用】",
    "code_evaluate": "【必用·Python表达式求值专用】",
}


def _enrich_mcp_description(original_name: str, description: str) -> str:
    """
    为 MCP 工具的 description 添加【必用】前缀

    策略：
        - 有映射的工具：加前缀 + 原文
        - 无映射的工具：保持原样

    Args:
        original_name: MCP 工具原始名（不带 mcp_ 前缀）
        description: 原始 description

    Returns:
        增强后的 description
    """
    prefix = MCP_TOOL_DESC_PREFIX_MAP.get(original_name, "")
    if prefix:
        return f"{prefix} {description}"
    return description


async def load_mcp_tools() -> List[StructuredTool]:
    """
    从 MCP Server 动态加载所有工具并包装为 LangChain StructuredTool

    流程：
    1. 检查 MCP Server 是否健康
    2. 调用 /mcp/tools/list 获取工具列表
    3. 为每个工具动态生成 Pydantic 模型 + 包装函数
    4. **v4 新增**：为 description 添加【必用】前缀
    5. 返回 StructuredTool 列表

    Returns:
        LangChain StructuredTool 列表（工具名带 mcp_ 前缀）
    """
    logger.info("=" * 50)
    logger.info("开始加载 MCP 工具")
    logger.info(f"MCP Server 地址: {settings.MCP_SERVER_URL}")

    # 1. 健康检查
    try:
        healthy = await mcp_client.health_check()
        if not healthy:
            logger.warning("MCP Server 不可用，跳过动态加载")
            return []
    except Exception as e:
        logger.warning(f"MCP Server 健康检查失败: {e}，跳过动态加载")
        return []

    # 2. 获取工具列表
    try:
        mcp_tool_list = await mcp_client.list_tools()
    except Exception as e:
        logger.warning(f"获取 MCP 工具列表失败: {e}，跳过动态加载")
        return []

    if not mcp_tool_list:
        logger.info("MCP Server 未注册任何工具")
        return []

    # 3. 逐个包装为 StructuredTool
    langchain_tools: List[StructuredTool] = []

    for tool_info in mcp_tool_list:
        original_name = tool_info["name"]
        wrapped_name = f"{MCP_TOOL_PREFIX}{original_name}"
        # v4：description 加上【必用】前缀
        raw_description = tool_info.get("description", "无描述")
        description = _enrich_mcp_description(original_name, raw_description)
        parameters = tool_info.get("parameters", {})

        try:
            # 动态生成 Pydantic 参数模型
            input_schema = _json_schema_to_pydantic_model(original_name, parameters)

            # 创建异步调用函数（使用默认参数绑定避免闭包问题）
            async def call_fn(_name=original_name, **kwargs):
                return await _execute_mcp_tool(_name, kwargs)

            # 包装为 StructuredTool
            structured_tool = StructuredTool(
                name=wrapped_name,
                description=description,
                func=None,  # 仅使用异步
                coroutine=call_fn,
                args_schema=input_schema,
            )

            langchain_tools.append(structured_tool)
            logger.info(f"  [MCP] {wrapped_name} ← {description[:60]}")

        except Exception as e:
            logger.warning(f"  [MCP] {original_name} 包装失败: {e}，跳过")

    logger.info(f"MCP 工具加载完成: 成功 {len(langchain_tools)}/{len(mcp_tool_list)} 个")
    logger.info("=" * 50)

    return langchain_tools


# ============================================================
# 启动时打印工具列表（供 main.py 调用）
# ============================================================

async def print_available_tools(local_tools: list) -> None:
    """
    启动时打印所有可用工具列表（本地 + MCP）

    Args:
        local_tools: 本地工具列表
    """
    from app.core.logging import get_logger
    log = get_logger(__name__)

    log.info("=" * 60)
    log.info("可用工具列表")
    log.info("=" * 60)

    # 本地工具
    log.info(f"[本地工具] 共 {len(local_tools)} 个:")
    for t in local_tools:
        log.info(f"  - {t.name}: {(t.description or '').split(chr(10))[0]}")

    # MCP 工具
    log.info(f"[MCP Server] 地址: {settings.MCP_SERVER_URL}")
    try:
        mcp_tool_list = await mcp_client.list_tools()
        if mcp_tool_list:
            log.info(f"[MCP 工具] 共 {len(mcp_tool_list)} 个:")
            for t in mcp_tool_list:
                log.info(f"  - {MCP_TOOL_PREFIX}{t['name']}: {t.get('description', '无描述')[:50]}")
        else:
            log.info("[MCP 工具] 无可用工具")
    except Exception as e:
        log.warning(f"[MCP 工具] 获取失败: {e}")

    log.info("=" * 60)
