# -*- coding: utf-8 -*-
"""
A2A Server - 研究 Agent

专注于信息搜索和整理。
"""

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from config import Config


class ResearcherAgent:
    """研究 Agent - 信息搜索和整理"""
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model=Config.LLM_MODEL,
            api_key=Config.LLM_API_KEY,
            base_url=Config.LLM_BASE_URL,
            temperature=0.7
        )
        
        self.system_prompt = """你是一个专业的研究助手，擅长信息搜索和整理。

你的职责：
1. 分析用户的研究需求
2. 提供结构化的研究结果
3. 给出可靠的信息来源建议
4. 总结关键发现和洞察

请以专业、客观、有条理的方式回答问题。"""
    
    async def process(self, input_data: dict) -> dict:
        """
        处理研究任务
        
        Args:
            input_data: {"query": "研究问题", "context": "背景信息"}
        
        Returns:
            {"result": "研究结果", "sources": ["来源建议"]}
        """
        query = input_data.get("query", "")
        context = input_data.get("context", "")
        
        # 构建消息
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=f"研究问题：{query}\n\n背景信息：{context}")
        ]
        
        # 调用 LLM
        response = await self.llm.ainvoke(messages)
        
        return {
            "result": response.content,
            "sources": [
                "建议搜索学术数据库获取更多信息",
                "参考相关行业报告",
                "查阅官方文档和权威资料"
            ]
        }


# 全局实例
researcher_agent = ResearcherAgent()
