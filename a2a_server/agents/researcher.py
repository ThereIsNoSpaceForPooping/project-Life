# -*- coding: utf-8 -*-
"""
Researcher Agent
"""

import asyncio
from typing import Any, Dict, List

from agents.base import BaseAgent


class ResearcherAgent(BaseAgent):
    """
    研究助手 Agent

    职责：信息搜索、知识整理、文献综述。
    """

    def __init__(self) -> None:
        super().__init__(
            name="researcher",
            description="研究助手：负责信息搜索、知识整理、文献综述",
            skills=[
                {
                    "id": "research-search",
                    "name": "信息搜索",
                    "description": "针对用户问题搜索相关资料",
                    "tags": ["search", "research"],
                    "examples": ["搜索 AI 最新进展", "查找 Python 教程"],
                },
                {
                    "id": "research-summarize",
                    "name": "知识整理",
                    "description": "将搜集的信息整理为结构化知识",
                    "tags": ["summarize", "knowledge"],
                    "examples": ["总结机器学习基础概念"],
                },
            ],
        )

    async def run(
        self,
        user_text: str,
        history: List[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        await asyncio.sleep(0.2)

        intermediate: List[Dict[str, Any]] = [
            {
                "type": "message",
                "role": "agent",
                "text": f"[思考] 分析研究问题: {user_text[:50]}...",
            }
        ]

        output: str = (
            f"[Researcher] 已针对您的问题进行信息检索和整理。\n\n"
            f"问题: {user_text}\n\n"
            f"（研究结果占位 - 生产环境对接 RAG / Web 搜索）"
        )

        return {
            "output": output,
            "artifacts": [
                {
                    "name": "research-report",
                    "description": "研究结果报告",
                    "parts": [{"type": "text", "text": output}],
                }
            ],
            "intermediate": intermediate,
        }
