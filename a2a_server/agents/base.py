# -*- coding: utf-8 -*-
"""
A2A Agents - 基础接口
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List

logger: logging.Logger = logging.getLogger("a2a.agents.base")


class BaseAgent(ABC):
    """
    A2A Agent 抽象基类

    所有具体 Agent 必须实现 run() 方法。
    """

    def __init__(
        self,
        name: str,
        description: str,
        skills: List[Dict[str, Any]] = None,
    ) -> None:
        self.name: str = name
        self.description: str = description
        self.skills: List[Dict[str, Any]] = skills or []

    @abstractmethod
    async def run(
        self,
        user_text: str,
        history: List[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        执行 Agent 任务

        Args:
            user_text: 用户输入文本
            history: 历史消息列表

        Returns:
            {
                "output": "最终回复文本",
                "artifacts": [...],          # 可选，产物列表
                "intermediate": [...]         # 可选，中间消息
            }
        """
        raise NotImplementedError

    def get_skill_dicts(self) -> List[Dict[str, Any]]:
        """返回技能字典列表（用于 AgentCard）"""
        return self.skills
