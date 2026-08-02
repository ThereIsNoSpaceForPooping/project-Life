# -*- coding: utf-8 -*-
"""
A2A Server - 编码 Agent

专注于代码生成和审查。
"""

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from config import Config


class CoderAgent:
    """编码 Agent - 代码生成和审查"""
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model=Config.LLM_MODEL,
            api_key=Config.LLM_API_KEY,
            base_url=Config.LLM_BASE_URL,
            temperature=0.3  # 代码生成需要更低的温度
        )
        
        self.system_prompt = """你是一个专业的编程助手，擅长代码生成和审查。

你的职责：
1. 根据需求生成高质量代码
2. 提供代码审查和改进建议
3. 解释代码逻辑和最佳实践
4. 帮助调试和修复问题

请提供清晰、可维护、符合最佳实践的代码。"""
    
    async def process(self, input_data: dict) -> dict:
        """
        处理编码任务
        
        Args:
            input_data: {
                "task": "generate/review/explain",
                "requirement": "需求描述",
                "code": "待审查的代码"
            }
        
        Returns:
            {"result": "代码或审查结果", "explanation": "解释说明"}
        """
        task = input_data.get("task", "generate")
        requirement = input_data.get("requirement", "")
        code = input_data.get("code", "")
        
        # 根据任务类型构建提示
        if task == "generate":
            user_content = f"请根据以下需求生成代码：\n\n{requirement}"
        elif task == "review":
            user_content = f"请审查以下代码并提供改进建议：\n\n```python\n{code}\n```"
        elif task == "explain":
            user_content = f"请解释以下代码的逻辑：\n\n```python\n{code}\n```"
        else:
            user_content = requirement
        
        # 构建消息
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=user_content)
        ]
        
        # 调用 LLM
        response = await self.llm.ainvoke(messages)
        
        return {
            "result": response.content,
            "explanation": "代码已生成，请查看结果"
        }


# 全局实例
coder_agent = CoderAgent()
