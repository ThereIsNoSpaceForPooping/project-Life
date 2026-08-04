# -*- coding: utf-8 -*-
"""
A2A Server - Agent 注册表

集中管理所有 Agent。
"""

import logging
from agents.researcher import researcher_agent
from agents.coder import coder_agent
from agents.translator import translator_agent
from agents.analyzer import analyzer_agent

# 模块级 logger（修复 logger 未定义 bug）
logger = logging.getLogger(__name__)


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
        logger.info(f"[A2A] 调用 Agent: {agent_name}, 输入: {input_data}")
        
        agent = self.get_agent(agent_name)
        
        if not agent:
            logger.error(f"[A2A] Agent 不存在: {agent_name}")
            return {"error": f"Agent 不存在: {agent_name}"}
        
        try:
            result = await agent.process(input_data)
            logger.info(f"[A2A] Agent {agent_name} 执行成功, 返回: {result}")
            return result
        except Exception as e:
            logger.error(f"[A2A] Agent {agent_name} 执行失败: {str(e)}")
            return {"error": f"Agent 执行失败: {str(e)}"}


# 全局 Agent 注册表
agent_registry = AgentRegistry()
