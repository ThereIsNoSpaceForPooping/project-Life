# -*- coding: utf-8 -*-
"""
MCP Server - HTTP 工具

提供 HTTP 请求功能。
"""

import httpx
from typing import Optional, Dict, Any


class HttpTools:
    """HTTP 操作工具集"""
    
    @staticmethod
    async def http_request(
        url: str,
        method: str = "GET",
        headers: Dict[str, str] = None,
        body: Dict[str, Any] = None,
        timeout: int = 30
    ) -> dict:
        """
        发送 HTTP 请求
        
        Args:
            url: 请求 URL
            method: HTTP 方法（GET/POST/PUT/DELETE）
            headers: 请求头
            body: 请求体（JSON）
            timeout: 超时时间（秒）
        
        Returns:
            {"status": 200, "headers": {...}, "body": "..."}
        """
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(
                    method=method.upper(),
                    url=url,
                    headers=headers or {},
                    json=body if body else None
                )
                
                # 尝试解析 JSON
                try:
                    response_body = response.json()
                except:
                    response_body = response.text
                
                return {
                    "status": response.status_code,
                    "headers": dict(response.headers),
                    "body": response_body
                }
        
        except httpx.TimeoutException:
            return {"error": f"请求超时: {timeout}秒"}
        except Exception as e:
            return {"error": f"请求失败: {str(e)}"}
    
    @staticmethod
    async def http_get(url: str, headers: Dict[str, str] = None) -> dict:
        """
        发送 GET 请求
        
        Args:
            url: 请求 URL
            headers: 请求头
        
        Returns:
            {"status": 200, "body": "..."}
        """
        return await HttpTools.http_request(url, "GET", headers)
    
    @staticmethod
    async def http_post(url: str, body: Dict[str, Any], headers: Dict[str, str] = None) -> dict:
        """
        发送 POST 请求
        
        Args:
            url: 请求 URL
            body: 请求体（JSON）
            headers: 请求头
        
        Returns:
            {"status": 200, "body": "..."}
        """
        return await HttpTools.http_request(url, "POST", headers, body)


# 工具注册信息
HTTP_TOOLS = [
    {
        "name": "http_request",
        "description": "发送 HTTP 请求（支持 GET/POST/PUT/DELETE）",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "请求 URL"
                },
                "method": {
                    "type": "string",
                    "description": "HTTP 方法",
                    "enum": ["GET", "POST", "PUT", "DELETE"],
                    "default": "GET"
                },
                "headers": {
                    "type": "object",
                    "description": "请求头"
                },
                "body": {
                    "type": "object",
                    "description": "请求体（JSON）"
                },
                "timeout": {
                    "type": "integer",
                    "description": "超时时间（秒）",
                    "default": 30
                }
            },
            "required": ["url"]
        },
        "handler": HttpTools.http_request
    },
    {
        "name": "http_get",
        "description": "发送 GET 请求",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "请求 URL"
                },
                "headers": {
                    "type": "object",
                    "description": "请求头"
                }
            },
            "required": ["url"]
        },
        "handler": HttpTools.http_get
    },
    {
        "name": "http_post",
        "description": "发送 POST 请求",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "请求 URL"
                },
                "body": {
                    "type": "object",
                    "description": "请求体（JSON）"
                },
                "headers": {
                    "type": "object",
                    "description": "请求头"
                }
            },
            "required": ["url", "body"]
        },
        "handler": HttpTools.http_post
    }
]
