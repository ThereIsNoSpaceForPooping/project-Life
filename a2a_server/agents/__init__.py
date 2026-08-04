# -*- coding: utf-8 -*-
"""A2A Server Agent 模块"""

from agents.registry import agent_registry, AgentRegistry
from agents.researcher import researcher_agent, ResearcherAgent
from agents.coder import coder_agent, CoderAgent
from agents.translator import translator_agent, TranslatorAgent
from agents.analyzer import analyzer_agent, AnalyzerAgent

__all__ = [
    "agent_registry",
    "AgentRegistry",
    "researcher_agent",
    "ResearcherAgent",
    "coder_agent",
    "CoderAgent",
    "translator_agent",
    "TranslatorAgent",
    "analyzer_agent",
    "AnalyzerAgent",
]
