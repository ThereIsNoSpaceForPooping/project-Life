# -*- coding: utf-8 -*-
"""
LLM 实例管理（共享组件）

提供统一的 get_llm() 工厂函数，所有图通过它获取 LLM 实例。
"""

from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def get_llm(provider: str = None, model: str = None, temperature: float = None) -> ChatOpenAI:
    """
    获取 LLM 实例

    根据配置创建对应的 LLM 实例。
    支持 MiniMax 和通义千问（DashScope）。

    Args:
        provider: LLM 提供商（minimax / dashscope）
        model: 模型名称（不指定则使用默认模型）
        temperature: 温度参数（0.0-2.0，越高越随机）

    Returns:
        ChatOpenAI: LLM 实例

    学习要点：
    - ChatOpenAI 是 LangChain 的统一接口
    - 通过 base_url 可以对接不同的 LLM 提供商
    - streaming=True 启用流式输出
    """
    provider = provider or settings.DEFAULT_PROVIDER
    temperature = temperature if temperature is not None else settings.TEMPERATURE

    # 根据 provider 选择对应配置
    if provider == "minimax":
        return ChatOpenAI(
            model=model or settings.MINIMAX_MODEL,
            api_key=settings.MINIMAX_API_KEY,
            base_url=settings.MINIMAX_BASE_URL,
            temperature=temperature,
            streaming=True,
        )
    elif provider == "dashscope":
        return ChatOpenAI(
            model=model or settings.DASHSCOPE_MODEL,
            api_key=settings.DASHSCOPE_API_KEY,
            base_url=settings.DASHSCOPE_BASE_URL,
            temperature=temperature,
            streaming=True,
        )
    else:
        raise ValueError(f"不支持的 provider: {provider}")
