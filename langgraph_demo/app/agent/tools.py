# -*- coding: utf-8 -*-
"""
Agent 工具定义

定义智能体可以调用的工具函数
支持真实 API 调用和模拟数据两种模式
"""

import os
import time
import httpx
from typing import Optional
from langchain_core.tools import tool
from app.core.logging import get_logger

logger = get_logger(__name__)

# ============================================================
# 配置
# ============================================================
# 是否使用真实 API（通过环境变量控制）
USE_REAL_API = os.getenv("USE_REAL_API", "true").lower() == "true"
# 天气 API Key（和风天气免费申请: https://dev.qweather.com/）
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "")
# 搜索 API（DuckDuckGo 免费，无需 Key）
SEARCH_MAX_RESULTS = int(os.getenv("SEARCH_MAX_RESULTS", "5"))


# ============================================================
# 工具1: 天气查询
# ============================================================
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
    
    if USE_REAL_API and WEATHER_API_KEY:
        return _get_weather_real(city)
    else:
        return _get_weather_mock(city)


def _get_weather_real(city: str) -> str:
    """使用和风天气 API 获取真实天气"""
    try:
        # 1. 先查询城市 ID
        geo_url = "https://geoapi.qweather.com/v2/city/lookup"
        geo_params = {
            "location": city,
            "key": WEATHER_API_KEY,
        }
        with httpx.Client(timeout=10) as client:
            geo_resp = client.get(geo_url, params=geo_params)
            geo_data = geo_resp.json()
            
            if geo_data.get("code") != "200" or not geo_data.get("location"):
                return f"抱歉，无法找到城市: {city}"
            
            location = geo_data["location"][0]
            city_id = location["id"]
            city_name = location["name"]
            
            # 2. 获取实时天气
            weather_url = "https://devapi.qweather.com/v7/weather/now"
            weather_params = {
                "location": city_id,
                "key": WEATHER_API_KEY,
            }
            weather_resp = client.get(weather_url, params=weather_params)
            weather_data = weather_resp.json()
            
            if weather_data.get("code") != "200":
                return f"抱歉，获取天气数据失败"
            
            now = weather_data["now"]
            return (
                f"{city_name}天气: {now['text']}，"
                f"温度 {now['temp']}°C，"
                f"体感 {now['feelsLike']}°C，"
                f"湿度 {now['humidity']}%，"
                f"风向 {now['windDir']}，"
                f"风力 {now['windScale']}级"
            )
    except Exception as e:
        logger.error(f"真实天气 API 调用失败: {e}")
        return _get_weather_mock(city)


def _get_weather_mock(city: str) -> str:
    """模拟天气数据（开发/测试用）"""
    weather_data = {
        "北京": "晴天，25°C，湿度 40%",
        "上海": "多云，22°C，湿度 65%",
        "广州": "小雨，28°C，湿度 80%",
        "深圳": "阴天，26°C，湿度 70%",
        "杭州": "晴转多云，23°C，湿度 55%",
        "成都": "小雨，20°C，湿度 85%",
    }
    return weather_data.get(city, f"晴天，22°C，湿度 50%（模拟数据）")


# ============================================================
# 工具2: 数学计算
# ============================================================
@tool
def calculate(expression: str) -> str:
    """
    计算数学表达式
    
    Args:
        expression: 数学表达式，如 "2 + 3 * 4"、"100 / 7"
        
    Returns:
        str: 计算结果
    """
    logger.info(f"调用工具: calculate({expression})")
    try:
        # 安全计算：只允许数学运算，禁止其他操作
        allowed_names = {
            "abs": abs, "round": round, "min": min, "max": max,
            "pow": pow, "sum": sum, "int": int, "float": float,
        }
        result = eval(expression, {"__builtins__": {}}, allowed_names)
        return f"{expression} = {result}"
    except Exception as e:
        return f"计算错误: {str(e)}"


# ============================================================
# 工具3: 知识库搜索
# ============================================================
@tool
def search_knowledge(query: str) -> str:
    """
    搜索本地知识库
    
    Args:
        query: 搜索关键词
        
    Returns:
        str: 搜索结果
    """
    logger.info(f"调用工具: search_knowledge({query})")
    
    # 本地知识库（可扩展为向量数据库）
    knowledge_base = {
        "langgraph": "LangGraph 是一个用于构建有状态、多参与者 Agent 的框架，支持循环、分支和持久化",
        "langchain": "LangChain 是一个用于开发 LLM 应用的框架，提供模型、提示、链、Agent 等抽象",
        "agent": "智能体是能够感知环境并采取行动以达成目标的系统，通常由 LLM + 工具 + 记忆组成",
        "fastapi": "FastAPI 是一个基于 Python 的现代 Web 框架，用于构建高性能 API，支持异步和自动文档",
        "docker": "Docker 是一个容器化平台，可以将应用及其依赖打包成轻量级容器",
        "prompt": "Prompt 是发送给 LLM 的输入文本，用于引导模型生成期望的输出",
        "embedding": "Embedding 是将文本转换为向量表示的技术，用于语义搜索和相似度计算",
        "rag": "RAG（检索增强生成）是一种结合检索和生成的技术，通过检索相关知识来增强 LLM 的回答",
    }
    
    # 关键词匹配
    results = []
    query_lower = query.lower()
    for key, value in knowledge_base.items():
        if key in query_lower:
            results.append(f"【{key}】{value}")
    
    if results:
        return "\n".join(results)
    return f"未找到与'{query}'相关的知识"


# ============================================================
# 工具4: 网络搜索（DuckDuckGo，免费无需 Key）
# ============================================================
@tool
def web_search(query: str) -> str:
    """
    使用 DuckDuckGo 进行网络搜索
    
    Args:
        query: 搜索关键词
        
    Returns:
        str: 搜索结果摘要
    """
    logger.info(f"调用工具: web_search({query})")
    
    try:
        from duckduckgo_search import DDGS
        
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=SEARCH_MAX_RESULTS))
        
        if not results:
            return f"未找到与'{query}'相关的搜索结果"
        
        # 格式化搜索结果
        formatted = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "无标题")
            body = r.get("body", "无摘要")
            href = r.get("href", "")
            formatted.append(f"[{i}] {title}\n    {body}\n    链接: {href}")
        
        return "\n\n".join(formatted)
    
    except ImportError:
        logger.warning("duckduckgo-search 未安装，使用模拟搜索")
        return _web_search_mock(query)
    except Exception as e:
        logger.error(f"网络搜索失败: {e}")
        return f"搜索失败: {str(e)}"


def _web_search_mock(query: str) -> str:
    """模拟网络搜索（开发/测试用）"""
    return (
        f"[1] {query} - 维基百科\n"
        f"    关于 {query} 的详细介绍和背景知识\n"
        f"    链接: https://zh.wikipedia.org/wiki/{query}\n\n"
        f"[2] {query} 最新进展\n"
        f"    {query} 的最新发展和动态\n"
        f"    链接: https://example.com/{query}\n\n"
        f"[3] {query} 教程指南\n"
        f"    入门 {query} 的完整教程\n"
        f"    链接: https://example.com/{query}/guide\n\n"
        f"（模拟数据，安装 duckduckgo-search 可获取真实结果）"
    )


# ============================================================
# 工具5: 当前时间
# ============================================================
@tool
def get_current_time() -> str:
    """
    获取当前日期和时间
    
    Returns:
        str: 当前时间信息
    """
    logger.info("调用工具: get_current_time()")
    from datetime import datetime
    now = datetime.now()
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    weekday = weekdays[now.weekday()]
    return f"当前时间: {now.strftime('%Y年%m月%d日 %H:%M:%S')} {weekday}"


# ============================================================
# 工具列表
# ============================================================
TOOLS = [
    get_weather,
    calculate,
    search_knowledge,
    web_search,
    get_current_time,
]
