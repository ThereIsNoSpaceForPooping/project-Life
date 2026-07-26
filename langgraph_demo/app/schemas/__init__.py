# -*- coding: utf-8 -*-
"""
数据模型层

定义请求/响应的数据结构
"""

from app.schemas.chat import ChatRequest, ChatResponse, StreamChunk

__all__ = ["ChatRequest", "ChatResponse", "StreamChunk"]
