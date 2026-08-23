# -*- coding: utf-8 -*-
"""
A2A 工具动态加载器

启动时从 A2A Server 拉取 Agent Card，
将每个 Agent 包装为 LangChain StructuredTool，
使 Agent 能像本地工具一样调用远程 A2A Agent。

流程：
    启动 → A2AClient.discover() → 遍历 skills
        → 每个 skill 包装为 StructuredTool
    Agent → bind_tools(本地 + MCP + A2A 工具) → LLM 自主选择
    tool_node → A2A 工具走 a2a_client.send()
"""

import logging
from typing import Any, Dict, List, Optional, Type

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model

from app.agent.a2a.client import A2AClient
from app.core.config import settings
from app.core.logging import get_logger

logger: logging.Logger = get_logger(__name__)


# ============================================================
# A2A 工具名称前缀（用于在 LLM 视角下区分本地/MCP/A2A 工具）
# ============================================================
A2A_TOOL_PREFIX: str = "a2a_"


def is_a2a_tool(tool_name: str) -> bool:
    """判断是否为 A2A 工具（通过前缀）"""
    return tool_name.startswith(A2A_TOOL_PREFIX)


def a2a_original_name(tool_name: str) -> str:
    """去掉前缀，获取 A2A Agent 名称"""
    return tool_name[len(A2A_TOOL_PREFIX):] if is_a2a_tool(tool_name) else tool_name


# ============================================================
# A2A 工具加载
# ============================================================
class A2AToolsLoader:
    """
    A2A 工具动态加载器

    负责：
        1. 启动时拉取 Agent Card
        2. 为每个 Agent 生成对应工具
        3. 包装为 LangChain StructuredTool
    """

    def __init__(self, a2a_url: Optional[str] = None) -> None:
        """
        初始化

        Args:
            a2a_url: A2A Server URL（默认从 settings.A2A_SERVER_URL 读取）
        """
        self.a2a_url: str = (
            a2a_url
            or getattr(settings, "A2A_SERVER_URL", None)
            or "http://localhost:8002"
        )
        self.client: Optional[A2AClient] = None
        self.tools: List[StructuredTool] = []

    async def load(self) -> List[StructuredTool]:
        """
        加载 A2A 工具

        Returns:
            LangChain StructuredTool 列表
        """
        logger.info("[A2ALoader] 正在连接 A2A Server: %s", self.a2a_url)
        self.client = A2AClient(base_url=self.a2a_url)

        try:
            await self.client.connect()
            agent_card: Dict[str, Any] = await self.client.discover()
        except Exception as exc:
            logger.error(
                "[A2ALoader] 连接 A2A Server 失败: %s（Agent 将只能使用本地/MCP 工具）",
                exc,
            )
            await self.client.close()
            self.client = None
            return []

        # 从 AgentCard 的 skills 中提取 Agent 列表
        # 注意：我们的 Server 把每个 Agent 作为一个 skill 暴露
        skills: List[Dict[str, Any]] = agent_card.get("skills", [])

        # 去重（按 agent name 前缀）
        agent_names: set = set()
        for skill in skills:
            skill_id: str = skill.get("id", "")
            agent_name: str = skill_id.split("-")[0] if "-" in skill_id else skill_id
            agent_names.add(agent_name)

        # 为每个 Agent 构造工具
        self.tools = [
            self._wrap_agent(agent_name, agent_card)
            for agent_name in agent_names
        ]

        logger.info(
            "[A2ALoader] 已加载 %d 个 A2A Agent 工具: %s",
            len(self.tools),
            [t.name for t in self.tools],
        )
        return self.tools

    def _wrap_agent(
        self,
        agent_name: str,
        agent_card: Dict[str, Any],
    ) -> StructuredTool:
        """
        将 A2A Agent 包装为 LangChain StructuredTool

        Args:
            agent_name: Agent 名称
            agent_card: Agent Card 字典

        Returns:
            StructuredTool 实例
        """
        # 从 agent card 中找到该 agent 的所有 skill
        agent_skills: List[Dict[str, Any]] = [
            skill for skill in agent_card.get("skills", [])
            if skill.get("id", "").startswith(agent_name)
        ]

        # 构造工具描述
        skills_text: str = "\n".join(
            f"  - {s.get('name')}: {s.get('description')}"
            for s in agent_skills
        )
        description: str = (
            f"[A2A] 调用远程 Agent '{agent_name}'。\n"
            f"该 Agent 提供以下 skills：\n{skills_text}"
        )

        # 构造 Pydantic 参数模型
        args_schema: Type[BaseModel] = create_model(  # type: ignore[call-overload]
            f"{agent_name}_A2A_Schema",
            text=(
                str,
                Field(..., description="发送给 Agent 的任务文本"),
            ),
        )

        # 异步执行函数
        async def _call(**kwargs: Any) -> str:
            if not self.client:
                return "A2A Client 未连接"
            try:
                text: str = kwargs.get("text", "")
                task: Dict[str, Any] = await self.client.send(
                    text=text,
                    agent_name=agent_name,
                )
                if task.get("error"):
                    return f"任务失败: {task['error']}"

                # 提取最终回复
                artifacts: List[Dict[str, Any]] = task.get("artifacts", [])
                if artifacts:
                    parts: List[Dict[str, Any]] = artifacts[0].get("parts", [])
                    return "\n".join(
                        p.get("text", "")
                        for p in parts
                        if p.get("type") == "text"
                    )

                # 备选：从 messages 中提取
                messages: List[Dict[str, Any]] = task.get("messages", [])
                agent_msgs: List[Dict[str, Any]] = [
                    m for m in messages if m.get("role") == "agent"
                ]
                if agent_msgs:
                    parts = agent_msgs[-1].get("parts", [])
                    return "\n".join(
                        p.get("text", "")
                        for p in parts
                        if p.get("type") == "text"
                    )

                return f"任务 {task.get('id', 'unknown')} 状态: {task.get('status', {}).get('state')}"
            except Exception as exc:
                return f"A2A 调用失败: {exc}"

        return StructuredTool(
            name=f"{A2A_TOOL_PREFIX}{agent_name}",
            description=description,
            args_schema=args_schema,
            coroutine=_call,
        )

    async def close(self) -> None:
        """关闭 A2A 连接"""
        if self.client:
            await self.client.close()
            self.client = None
            self.tools = []


# ============================================================
# 全局加载器
# ============================================================
a2a_loader: Optional[A2AToolsLoader] = None


async def load_a2a_tools() -> List[StructuredTool]:
    """
    全局入口：加载 A2A 工具

    Returns:
        LangChain StructuredTool 列表
    """
    global a2a_loader
    if a2a_loader is None:
        a2a_loader = A2AToolsLoader()
    return await a2a_loader.load()


async def close_a2a_tools() -> None:
    """关闭 A2A 连接"""
    global a2a_loader
    if a2a_loader:
        await a2a_loader.close()
        a2a_loader = None
