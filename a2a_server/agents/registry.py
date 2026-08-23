# -*- coding: utf-8 -*-
"""
A2A Agents - 注册表
"""

import logging
from typing import Any, Dict, List, Optional

from agents.base import BaseAgent
from agents.researcher import ResearcherAgent
from agents.coder import CoderAgent
from agents.translator import TranslatorAgent
from agents.analyzer import AnalyzerAgent

logger: logging.Logger = logging.getLogger("a2a.agents.registry")


class AgentRegistry:
    """
    Agent 注册表

    集中管理所有可用 Agent，并提供 AgentCard 生成。
    """

    def __init__(self) -> None:
        self._agents: Dict[str, BaseAgent] = {}
        self._register_default_agents()

    def _register_default_agents(self) -> None:
        """注册默认的 4 个 Agent"""
        for agent in (
            ResearcherAgent(),
            CoderAgent(),
            TranslatorAgent(),
            AnalyzerAgent(),
        ):
            self.register(agent)

    def register(self, agent: BaseAgent) -> None:
        """
        注册 Agent

        Args:
            agent: Agent 实例
        """
        self._agents[agent.name] = agent
        logger.info(
            "[Registry] 注册 Agent: %s, skills=%d",
            agent.name, len(agent.skills),
        )

    def get_agent(self, name: str) -> Optional[BaseAgent]:
        """获取 Agent"""
        return self._agents.get(name)

    def has_agent(self, name: str) -> bool:
        """是否存在"""
        return name in self._agents

    def list_agents(self) -> List[BaseAgent]:
        """所有 Agent"""
        return list(self._agents.values())

    def list_agent_names(self) -> List[str]:
        """所有 Agent 名称"""
        return list(self._agents.keys())

    def get_all_skills(self) -> List[Dict[str, Any]]:
        """所有技能（用于 AgentCard）"""
        skills: List[Dict[str, Any]] = []
        for agent in self._agents.values():
            skills.extend(agent.get_skill_dicts())
        return skills


# 全局单例
agent_registry: AgentRegistry = AgentRegistry()
