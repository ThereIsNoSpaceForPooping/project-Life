# -*- coding: utf-8 -*-
"""
Coder Agent
"""

import asyncio
from typing import Any, Dict, List

from agents.base import BaseAgent


class CoderAgent(BaseAgent):
    """
    编码助手 Agent
    """

    def __init__(self) -> None:
        super().__init__(
            name="coder",
            description="编码助手：负责代码生成、代码审查、Bug 修复",
            skills=[
                {
                    "id": "code-generate",
                    "name": "代码生成",
                    "description": "根据需求生成 Python/JS/Go 等代码",
                    "tags": ["code", "generate"],
                    "examples": ["写一个快速排序", "实现 REST API"],
                },
                {
                    "id": "code-review",
                    "name": "代码审查",
                    "description": "审查代码质量、风格、性能",
                    "tags": ["code", "review"],
                    "examples": ["审查这段 Python 代码"],
                },
            ],
        )

    async def run(
        self,
        user_text: str,
        history: List[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        await asyncio.sleep(0.2)

        output: str = (
            f"[Coder] 收到编码任务。\n\n"
            f"需求: {user_text}\n\n"
            f"（代码实现占位 - 生产环境对接 LLM Code 模型）"
        )

        return {
            "output": output,
            "artifacts": [
                {
                    "name": "code-output",
                    "description": "代码产物",
                    "parts": [{"type": "text", "text": output}],
                }
            ],
        }
