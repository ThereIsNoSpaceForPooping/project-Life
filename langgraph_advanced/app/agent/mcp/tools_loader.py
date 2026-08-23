# -*- coding: utf-8 -*-
"""
MCP 工具动态加载器

启动时从 MCP Server 获取所有可用工具，
将每个 MCP 工具包装为 LangChain StructuredTool，
使 Agent 能像本地工具一样调用 MCP 工具。

流程：
    启动 → ClientSession.list_tools() → 包装为 StructuredTool
    Agent → bind_tools(本地 + MCP 工具) → LLM 自主选择
    tool_node → 本地工具直接执行 / MCP 工具走 ClientSession
"""

import json
from typing import Any, Dict, List, Optional, Type

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model

from app.agent.mcp.client import MCPClient
from app.core.config import settings
from app.core.logging import get_logger

logger: logging.Logger = get_logger(__name__)


# ============================================================
# MCP 工具名称前缀（用于在 LLM 视角下区分本地/MCP 工具）
# ============================================================
MCP_TOOL_PREFIX: str = "mcp_"


def is_mcp_tool(tool_name: str) -> bool:
    """判断是否为 MCP 工具（通过前缀）"""
    return tool_name.startswith(MCP_TOOL_PREFIX)


def mcp_original_name(tool_name: str) -> str:
    """去掉前缀，获取 MCP Server 上的原始名称"""
    return tool_name[len(MCP_TOOL_PREFIX):] if is_mcp_tool(tool_name) else tool_name


# ============================================================
# JSON Schema → Pydantic Model
# ============================================================
def _schema_to_pydantic(
    name: str,
    schema: Dict[str, Any],
) -> Type[BaseModel]:
    """
    将 MCP inputSchema（JSON Schema）转换为 Pydantic BaseModel

    Args:
        name: 模型名
        schema: JSON Schema 字典

    Returns:
        Pydantic 模型类
    """
    properties: Dict[str, Any] = schema.get("properties", {})
    required: List[str] = schema.get("required", [])

    fields: Dict[str, Any] = {}
    for prop_name, prop_schema in properties.items():
        # 解析类型
        prop_type: Any = _json_type_to_python(prop_schema)

        # 描述
        description: str = prop_schema.get("description", "")

        # 必填 vs 可选
        if prop_name in required:
            fields[prop_name] = (prop_type, Field(..., description=description))
        else:
            default: Any = prop_schema.get("default", None)
            fields[prop_name] = (
                prop_type,
                Field(default=default, description=description),
            )

    return create_model(name, **fields)  # type: ignore[call-overload]


def _json_type_to_python(prop_schema: Dict[str, Any]) -> Any:
    """
    JSON Schema 类型 → Python 类型映射

    Args:
        prop_schema: JSON Schema 字段

    Returns:
        Python 类型
    """
    json_type: str = prop_schema.get("type", "string")

    if json_type == "string":
        return str
    if json_type == "integer":
        return int
    if json_type == "number":
        return float
    if json_type == "boolean":
        return bool
    if json_type == "array":
        return List[Any]
    if json_type == "object":
        return Dict[str, Any]
    return Any


# ============================================================
# MCP 工具加载
# ============================================================
class MCPToolsLoader:
    """
    MCP 工具动态加载器

    负责：
        1. 启动时连接 MCP Server
        2. 拉取工具列表
        3. 包装为 LangChain StructuredTool
    """

    def __init__(self, mcp_url: Optional[str] = None) -> None:
        """
        初始化

        Args:
            mcp_url: MCP Server URL（默认从 settings.MCP_SERVER_URL 读取）
        """
        self.mcp_url: str = (
            mcp_url
            or getattr(settings, "MCP_SERVER_URL", None)
            or "http://localhost:8001/mcp"
        )
        self.client: Optional[MCPClient] = None
        self.tools: List[StructuredTool] = []

    async def load(self) -> List[StructuredTool]:
        """
        加载 MCP 工具

        Returns:
            LangChain StructuredTool 列表
        """
        logger.info("[MCPLoader] 正在连接 MCP Server: %s", self.mcp_url)
        self.client = MCPClient(url=self.mcp_url)
        try:
            await self.client.connect()
        except Exception as exc:
            logger.error(
                "[MCPLoader] 连接 MCP Server 失败: %s（Agent 将只能使用本地工具）",
                exc,
            )
            return []

        # 拉取工具列表
        try:
            mcp_tools: List[Dict[str, Any]] = await self.client.list_tools()
        except Exception as exc:
            logger.error("[MCPLoader] 拉取工具列表失败: %s", exc)
            await self.client.close()
            return []

        # 包装为 StructuredTool
        self.tools = [
            self._wrap_tool(tool_def) for tool_def in mcp_tools
        ]

        logger.info(
            "[MCPLoader] 已加载 %d 个 MCP 工具: %s",
            len(self.tools),
            [t.name for t in self.tools],
        )
        return self.tools

    def _wrap_tool(self, tool_def: Dict[str, Any]) -> StructuredTool:
        """
        将 MCP 工具包装为 LangChain StructuredTool

        Args:
            tool_def: MCP 工具定义

        Returns:
            StructuredTool 实例
        """
        original_name: str = tool_def["name"]
        description: str = tool_def.get("description", "")
        input_schema: Dict[str, Any] = tool_def.get("inputSchema", {})

        # 构造 Pydantic 参数模型
        try:
            args_schema: Type[BaseModel] = _schema_to_pydantic(
                name=f"{original_name}_Schema",
                schema=input_schema,
            )
        except Exception as exc:
            logger.warning(
                "[MCPLoader] 工具 '%s' Schema 解析失败，使用 Any: %s",
                original_name, exc,
            )
            args_schema = create_model(  # type: ignore[call-overload]
                f"{original_name}_Schema",
                kwargs=(Optional[Dict[str, Any]], None),
            )

        # 异步执行函数
        async def _call(**kwargs: Any) -> str:
            if not self.client:
                return "MCP Client 未连接"
            try:
                result: Dict[str, Any] = await self.client.call_tool(
                    original_name, kwargs
                )
                if result.get("isError"):
                    return f"工具错误: {result.get('content')}"
                # 拼接文本 content
                return "\n".join(
                    item.get("text", "")
                    for item in result.get("content", [])
                    if item.get("type") == "text"
                )
            except Exception as exc:
                return f"调用失败: {exc}"

        return StructuredTool(
            name=f"{MCP_TOOL_PREFIX}{original_name}",
            description=f"[MCP] {description}",
            args_schema=args_schema,
            coroutine=_call,
        )

    async def close(self) -> None:
        """关闭 MCP 连接"""
        if self.client:
            await self.client.close()
            self.client = None
            self.tools = []


# ============================================================
# 全局加载器
# ============================================================
mcp_loader: Optional[MCPToolsLoader] = None


async def load_mcp_tools() -> List[StructuredTool]:
    """
    全局入口：加载 MCP 工具

    Returns:
        LangChain StructuredTool 列表
    """
    global mcp_loader
    if mcp_loader is None:
        mcp_loader = MCPToolsLoader()
    return await mcp_loader.load()


async def close_mcp_tools() -> None:
    """关闭 MCP 连接"""
    global mcp_loader
    if mcp_loader:
        await mcp_loader.close()
        mcp_loader = None
