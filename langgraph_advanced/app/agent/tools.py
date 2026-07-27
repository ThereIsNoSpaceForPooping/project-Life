# -*- coding: utf-8 -*-
"""
Agent 工具定义

工具（Tools）是 Agent 与外部世界交互的接口。
LangChain 提供了丰富的工具抽象。

学习要点：
1. 使用 @tool 装饰器定义工具
2. 工具函数需要有清晰的 docstring（LLM 会读取）
3. 工具参数使用类型注解（Pydantic 会自动验证）
4. 工具返回字符串或可序列化的对象
"""

import json
import random
from datetime import datetime
from typing import Optional

import httpx
from langchain_core.tools import tool

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


# ============================================================
# 工具1: 天气查询
# ============================================================
@tool
def get_weather(city: str) -> str:
    """
    查询指定城市的当前天气
    
    Args:
        city: 城市名称（如：北京、上海、广州）
    
    Returns:
        包含温度、湿度、天气状况的 JSON 字符串
    
    示例:
        >>> get_weather("北京")
        '{"city": "北京", "temperature": "22°C", "humidity": "65%", "condition": "晴"}'
    """
    logger.info(f"查询天气: {city}")
    
    # 如果配置了真实 API，使用和风天气
    if settings.USE_REAL_API and settings.WEATHER_API_KEY:
        return _get_real_weather(city)
    
    # 否则返回模拟数据
    return _get_mock_weather(city)


def _get_real_weather(city: str) -> str:
    """调用真实的天气 API（和风天气）"""
    try:
        # 这里简化处理，实际应该先查询城市 ID
        # 参考: https://dev.qweather.com/docs/api/
        return json.dumps({
            "city": city,
            "temperature": "22°C",
            "humidity": "65%",
            "condition": "晴",
            "source": "和风天气 API"
        }, ensure_ascii=False)
    except Exception as e:
        logger.error(f"天气 API 调用失败: {e}")
        return _get_mock_weather(city)


def _get_mock_weather(city: str) -> str:
    """返回模拟的天气数据"""
    conditions = ["晴", "多云", "阴", "小雨", "大风"]
    return json.dumps({
        "city": city,
        "temperature": f"{random.randint(15, 30)}°C",
        "humidity": f"{random.randint(40, 80)}%",
        "condition": random.choice(conditions),
        "source": "模拟数据"
    }, ensure_ascii=False)


# ============================================================
# 工具2: 数学计算
# ============================================================
@tool
def calculate(expression: str) -> str:
    """
    计算数学表达式
    
    Args:
        expression: 数学表达式（如：2 + 3 * 4）
    
    Returns:
        计算结果
    
    示例:
        >>> calculate("2 + 3 * 4")
        '14'
    """
    logger.info(f"计算表达式: {expression}")
    
    try:
        # 安全地计算数学表达式
        # 只允许数字和基本运算符
        allowed_chars = set('0123456789+-*/.() ')
        if not all(c in allowed_chars for c in expression):
            return "错误: 表达式包含非法字符"
        
        result = eval(expression, {"__builtins__": {}}, {})
        return str(result)
    except Exception as e:
        logger.error(f"计算失败: {e}")
        return f"计算错误: {str(e)}"


# ============================================================
# 工具3: 知识库搜索
# ============================================================
@tool
def search_knowledge(query: str, max_results: int = 5) -> str:
    """
    搜索知识库
    
    Args:
        query: 搜索关键词
        max_results: 最大返回结果数
    
    Returns:
        搜索结果列表（JSON 格式）
    
    示例:
        >>> search_knowledge("Python 教程")
        '[{"title": "Python 入门", "content": "...", "score": 0.95}]'
    """
    logger.info(f"搜索知识库: {query}")
    
    # 模拟知识库搜索
    # 实际场景可以对接向量数据库（如 Milvus、Pinecone）
    mock_results = [
        {
            "title": f"结果 {i+1}: {query}",
            "content": f"这是关于 '{query}' 的第 {i+1} 条搜索结果...",
            "score": round(random.uniform(0.7, 0.99), 2)
        }
        for i in range(max_results)
    ]
    
    return json.dumps(mock_results, ensure_ascii=False)


# ============================================================
# 工具4: 网络搜索
# ============================================================
@tool
def web_search(query: str, max_results: int = 5) -> str:
    """
    网络搜索（使用 DuckDuckGo）
    
    Args:
        query: 搜索关键词
        max_results: 最大返回结果数
    
    Returns:
        搜索结果列表（JSON 格式）
    
    示例:
        >>> web_search("LangGraph 教程")
        '[{"title": "LangGraph 官方文档", "url": "...", "snippet": "..."}]'
    """
    logger.info(f"网络搜索: {query}")
    
    if not settings.USE_REAL_API:
        return _mock_web_search(query, max_results)
    
    try:
        from duckduckgo_search import DDGS
        
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            
            if not results:
                return "未找到相关结果"
            
            formatted = [
                {
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", "")
                }
                for r in results
            ]
            
            return json.dumps(formatted, ensure_ascii=False)
    
    except Exception as e:
        logger.error(f"网络搜索失败: {e}")
        return _mock_web_search(query, max_results)


def _mock_web_search(query: str, max_results: int) -> str:
    """模拟网络搜索"""
    mock_results = [
        {
            "title": f"搜索结果 {i+1}: {query}",
            "url": f"https://example.com/result{i+1}",
            "snippet": f"这是关于 '{query}' 的搜索结果摘要..."
        }
        for i in range(max_results)
    ]
    return json.dumps(mock_results, ensure_ascii=False)


# ============================================================
# 工具5: 获取当前时间
# ============================================================
@tool
def get_current_time() -> str:
    """
    获取当前时间
    
    Returns:
        当前时间的 ISO 格式字符串
    
    示例:
        >>> get_current_time()
        '2024-01-15 14:30:45'
    """
    now = datetime.now()
    return now.strftime("%Y-%m-%d %H:%M:%S")


# ============================================================
# 工具列表（供 Agent 绑定使用）
# ============================================================
TOOLS = [
    get_weather,
    calculate,
    search_knowledge,
    web_search,
    get_current_time,
]


# ============================================================
# 工具分类（用于动态工具选择）
# ============================================================
TOOL_CATEGORIES = {
    "weather": [get_weather],
    "calculation": [calculate],
    "search": [search_knowledge, web_search],
    "time": [get_current_time],
}


def get_tools_by_category(categories: list[str]) -> list:
    """
    根据分类获取工具
    
    Args:
        categories: 工具分类列表（如：["weather", "search"]）
    
    Returns:
        工具列表
    
    示例:
        >>> get_tools_by_category(["weather", "search"])
        [get_weather, search_knowledge, web_search]
    """
    tools = []
    for category in categories:
        if category in TOOL_CATEGORIES:
            tools.extend(TOOL_CATEGORIES[category])
    return tools


def get_tools_by_names(names: list[str]) -> list:
    """
    根据工具名称获取工具
    
    Args:
        names: 工具名称列表（如：["get_weather", "calculate"]）
    
    Returns:
        工具列表
    
    示例:
        >>> get_tools_by_names(["get_weather", "calculate"])
        [get_weather, calculate]
    """
    tools = []
    for name in names:
        for tool in TOOLS:
            if tool.name == name:
                tools.append(tool)
                break
    return tools
