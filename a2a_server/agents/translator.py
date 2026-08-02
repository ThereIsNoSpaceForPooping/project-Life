# -*- coding: utf-8 -*-
"""
A2A Server - 翻译 Agent

专注于多语言翻译。
"""

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from config import Config


class TranslatorAgent:
    """翻译 Agent - 多语言翻译"""
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model=Config.LLM_MODEL,
            api_key=Config.LLM_API_KEY,
            base_url=Config.LLM_BASE_URL,
            temperature=0.3
        )
        
        self.system_prompt = """你是一个专业的翻译助手，精通多种语言。

你的职责：
1. 提供准确、流畅的翻译
2. 保持原文的语气和风格
3. 考虑文化差异和语境
4. 提供翻译说明和注意事项

请确保翻译质量高、易于理解。"""
    
    async def process(self, input_data: dict) -> dict:
        """
        处理翻译任务
        
        Args:
            input_data: {
                "text": "待翻译文本",
                "source_lang": "源语言",
                "target_lang": "目标语言"
            }
        
        Returns:
            {"translation": "翻译结果", "notes": "翻译说明"}
        """
        text = input_data.get("text", "")
        source_lang = input_data.get("source_lang", "auto")
        target_lang = input_data.get("target_lang", "中文")
        
        # 构建翻译提示
        if source_lang == "auto":
            user_content = f"请将以下文本翻译成{target_lang}：\n\n{text}"
        else:
            user_content = f"请将以下{source_lang}文本翻译成{target_lang}：\n\n{text}"
        
        # 构建消息
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=user_content)
        ]
        
        # 调用 LLM
        response = await self.llm.ainvoke(messages)
        
        return {
            "translation": response.content,
            "notes": f"从 {source_lang} 翻译到 {target_lang}"
        }


# 全局实例
translator_agent = TranslatorAgent()
