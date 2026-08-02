# -*- coding: utf-8 -*-
"""
A2A Server - Agent 注册表

集中管理所有 Agent。
"""

from agents.researcher import researcher_agent
from agents.coder import coder_agent
from agents.translator import translator_agent
from agents.analyzer import analyzer_agent


class AgentRegistry:
    """Agent 注册表"""
    
    def __init__(self):
        self._agents = {
            "researcher": {
                "instance": researcher_agent,
                "description": "研究助手 - 信息搜索和整理",
                "capabilities": ["search", "analyze", "summarize"]
            },
            "coder": {
                "instance": coder_agent,
                "description": "编码助手 - 代码生成和审查",
                "capabilities": ["generate", "review", "explain"]
            },
            "translator": {
                "instance": translator_agent,
                "description": "翻译助手 - 多语言翻译",
                "capabilities": ["translate"]
            },
            "analyzer": {
                "instance": analyzer_agent,
                "description": "分析助手 - 数据分析和洞察",
                "capabilities": ["trend", "pattern", "summary"]
            }
        }
    
    def get_agent(self, name: str):
        """获取 Agent 实例"""
        agent_info = self._agents.get(name)
        return agent_info["instance"] if agent_info else None
    
    def get_all_agents(self) -> list:
        """获取所有 Agent 列表"""
        return [
            {
                "name": name,
                "description": info["description"],
                "capabilities": info["capabilities"]
            }
            for name, info in self._agents.items()
        ]
    
    async def process_task(self, agent_name: str, input_data: dict) -> dict:
        """
        处理任务
        
        Args:
            agent_name: Agent 名称
            input_data: 输入数据
        
        Returns:
            处理结果
        """
        agent = self.get_agent(agent_name)
        
        if not agent:
            return {"error": f"Agent 不存在: {agent_name}"}
        
        try:
            return await agent.process(input_data)
        except Exception as e:
            return {"error": f"Agent 执行失败: {str(e)}"}


# 全局 Agent 注册表
agent_registry = AgentRegistry()
