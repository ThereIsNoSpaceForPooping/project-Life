# -*- coding: utf-8 -*-
"""
Agent 工具定义

定义智能体可以调用的工具函数
"""

from langchain_core.tools import tool
from app.core.logging import get_logger

logger = get_logger(__name__)


@tool
def get_weather(city: str) -> str:
    """
    获取指定城市的天气信息
    
    Args:
        city: 城市名称，如"北京"、"上海"
        
    Returns:
        str: 天气信息
    """
    logger.info(f"调用工具: get_weather({city})")
    # 模拟天气数据
    weather_data = {
        "北京": "晴天，25°C，湿度 40%",
        "上海": "多云，22°C，湿度 65%",
        "广州": "小雨，28°C，湿度 80%",
        "深圳": "阴天，26°C，湿度 70%",
    }
    return weather_data.get(city, f"抱歉，暂无{city}的天气数据")


@tool
def calculate(expression: str) -> str:
    """
    计算数学表达式
    
    Args:
        expression: 数学表达式，如 "2 + 3 * 4"
        
    Returns:
        str: 计算结果
    """
    logger.info(f"调用工具: calculate({expression})")
    try:
        # 安全计算（仅支持基本运算）
        result = eval(expression, {"__builtins__": {}})
        return f"{expression} = {result}"
    except Exception as e:
        return f"计算错误: {str(e)}"


@tool
def search_knowledge(query: str) -> str:
    """
    搜索知识库
    
    Args:
        query: 搜索关键词
        
    Returns:
        str: 搜索结果
    """
    logger.info(f"调用工具: search_knowledge({query})")
    # 模拟知识库搜索
    knowledge_base = {
        "langgraph": "LangGraph 是一个用于构建有状态、多参与者 Agent 的框架",
        "langchain": "LangChain 是一个用于开发 LLM 应用的框架",
        "agent": "智能体是能够感知环境并采取行动以达成目标的系统",
    }
    
    # 简单关键词匹配
    for key, value in knowledge_base.items():
        if key in query.lower():
            return value
    
    return f"未找到与'{query}'相关的知识"


# 工具列表
TOOLS = [get_weather, calculate, search_knowledge]
