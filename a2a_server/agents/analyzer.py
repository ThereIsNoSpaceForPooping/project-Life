# -*- coding: utf-8 -*-
"""
A2A Server - 分析 Agent

专注于数据分析和洞察。
"""

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from config import Config


class AnalyzerAgent:
    """分析 Agent - 数据分析和洞察"""
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model=Config.LLM_MODEL,
            api_key=Config.LLM_API_KEY,
            base_url=Config.LLM_BASE_URL,
            temperature=0.5
        )
        
        self.system_prompt = """你是一个专业的数据分析助手，擅长从数据中提取洞察。

你的职责：
1. 分析提供的数据或文本
2. 识别关键模式和趋势
3. 提供有价值的洞察和建议
4. 用清晰的方式呈现分析结果

请提供客观、有数据支持的分析。"""
    
    async def process(self, input_data: dict) -> dict:
        """
        处理分析任务
        
        Args:
            input_data: {
                "data": "待分析的数据或文本",
                "analysis_type": "类型：trend/pattern/summary"
            }
        
        Returns:
            {"analysis": "分析结果", "insights": ["洞察列表"]}
        """
        data = input_data.get("data", "")
        analysis_type = input_data.get("analysis_type", "summary")
        
        # 根据分析类型构建提示
        type_prompts = {
            "trend": "请分析以下数据的趋势：",
            "pattern": "请识别以下数据中的模式：",
            "summary": "请对以下内容进行总结分析："
        }
        
        prompt = type_prompts.get(analysis_type, type_prompts["summary"])
        user_content = f"{prompt}\n\n{data}"
        
        # 构建消息
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=user_content)
        ]
        
        # 调用 LLM
        response = await self.llm.ainvoke(messages)
        
        return {
            "analysis": response.content,
            "insights": [
                "关键发现已识别",
                "建议进一步验证",
                "可考虑相关因素的影响"
            ]
        }


# 全局实例
analyzer_agent = AnalyzerAgent()
