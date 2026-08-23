# -*- coding: utf-8 -*-
"""
MCP HTTP 请求工具

使用 FastMCP 的 @mcp.tool() 装饰器注册 3 个 HTTP 工具：
    - http_request：通用 HTTP 请求（GET/POST/PUT/DELETE/PATCH）
    - http_get：HTTP GET 简写
    - http_post：HTTP POST 简写

基于 httpx 异步客户端实现，支持超时控制、请求头与 JSON Body。
内置 SSRF 防护：禁止访问内网与本地回环地址。
"""

import ipaddress
import logging
import socket
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx

logger: logging.Logger = logging.getLogger("mcp.http")


# ============================================================
# SSRF 防护
# ============================================================
def _is_private_address(host: str) -> bool:
    """
    判断是否为内网/本地地址（SSRF 防护）

    拒绝访问：
        - 127.0.0.0/8（loopback）
        - 10.0.0.0/8（私网）
        - 172.16.0.0/12（私网）
        - 192.168.0.0/16（私网）
        - 169.254.0.0/16（link-local）
        - 0.0.0.0
        - ::1, fc00::/7 等 IPv6 内网

    Args:
        host: 主机名或 IP

    Returns:
        是否为内网地址
    """
    # 尝试解析为 IP
    try:
        ip: Any = ipaddress.ip_address(host)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
    except ValueError:
        pass

    # 解析域名
    try:
        resolved: str = socket.gethostbyname(host)
        ip = ipaddress.ip_address(resolved)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
    except (socket.gaierror, ValueError):
        return False


# ============================================================
# 通用 HTTP 请求执行器
# ============================================================
async def _do_request(
    method: str,
    url: str,
    headers: Optional[Dict[str, str]] = None,
    body: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    """
    实际执行 HTTP 请求

    Args:
        method: HTTP 方法
        url: 请求 URL
        headers: 请求头
        body: 请求体（会自动序列化为 JSON）
        timeout: 超时秒数

    Returns:
        包含 status / headers / body 的字典
    """
    # URL 校验
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return {
            "isError": True,
            "content": [{"type": "text", "text": f"非法 URL scheme: {parsed.scheme}"}],
        }

    if not parsed.hostname:
        return {
            "isError": True,
            "content": [{"type": "text", "text": "URL 缺少主机名"}],
        }

    # SSRF 防护
    if _is_private_address(parsed.hostname):
        return {
            "isError": True,
            "content": [
                {"type": "text", "text": f"禁止访问内网地址: {parsed.hostname}"}
            ],
        }

    # 限制最大响应体大小（防止 OOM）
    max_bytes: int = 5 * 1024 * 1024  # 5 MB

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response: httpx.Response = await client.request(
                method=method.upper(),
                url=url,
                headers=headers or {},
                json=body if body else None,
            )

            # 截断过大响应
            content_bytes: bytes = response.content
            truncated: bool = False
            if len(content_bytes) > max_bytes:
                content_bytes = content_bytes[:max_bytes]
                truncated = True

            # 解析响应体
            try:
                response_body: Any = response.json()
            except Exception:
                # 尝试文本解码
                try:
                    response_body = content_bytes.decode("utf-8", errors="replace")
                except Exception:
                    response_body = content_bytes.decode("latin-1", errors="replace")

            logger.info(
                "[%s] %s → %d (%d bytes%s)",
                method.upper(),
                url,
                response.status_code,
                len(content_bytes),
                " 截断" if truncated else "",
            )

            return {
                "status": response.status_code,
                "headers": dict(response.headers),
                "body": response_body,
                "truncated": truncated,
            }

    except httpx.TimeoutException:
        logger.warning("[%s] %s 超时 (%ds)", method.upper(), url, timeout)
        return {
            "isError": True,
            "content": [{"type": "text", "text": f"请求超时: {timeout}秒"}],
        }
    except httpx.RequestError as exc:
        logger.warning("[%s] %s 请求失败: %s", method.upper(), url, exc)
        return {
            "isError": True,
            "content": [{"type": "text", "text": f"请求失败: {exc}"}],
        }
    except Exception as exc:  # pragma: no cover
        logger.exception("[%s] %s 异常: %s", method.upper(), url, exc)
        return {
            "isError": True,
            "content": [{"type": "text", "text": f"未知错误: {exc}"}],
        }


# ============================================================
# 工具注册函数
# ============================================================
def register_http_tools(mcp: Any) -> int:
    """
    注册 HTTP 工具到 FastMCP 实例

    Args:
        mcp: FastMCP 实例

    Returns:
        注册的工具数量
    """

    # ============================================================
    # 工具 1：http_request（通用）
    # ============================================================
    @mcp.tool(
        name="http_request",
        description=(
            "发送 HTTP 请求（GET/POST/PUT/DELETE/PATCH）。"
            "支持自定义请求头、JSON Body、超时。"
            "【必用·HTTP通用请求专用】"
        ),
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,        # 访问开放互联网
        },
    )
    async def http_request(
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        body: Optional[Dict[str, Any]] = None,
        timeout: int = 30,
    ) -> Dict[str, Any]:
        """
        发送通用 HTTP 请求

        Args:
            url: 请求 URL
            method: HTTP 方法
            headers: 请求头
            body: 请求体（JSON）
            timeout: 超时秒数

        Returns:
            包含 status / headers / body 的字典
        """
        method_upper: str = method.upper()
        if method_upper not in ("GET", "POST", "PUT", "DELETE", "PATCH", "HEAD"):
            return {
                "isError": True,
                "content": [
                    {"type": "text", "text": f"不支持的 HTTP 方法: {method}"}
                ],
            }

        return await _do_request(method_upper, url, headers, body, timeout)

    # ============================================================
    # 工具 2：http_get（只读）
    # ============================================================
    @mcp.tool(
        name="http_get",
        description=(
            "发送 HTTP GET 请求。返回响应状态码、响应头、响应体。"
            "【必用·HTTP GET 专用】"
        ),
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def http_get(
        url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 30,
    ) -> Dict[str, Any]:
        """
        发送 HTTP GET 请求

        Args:
            url: 请求 URL
            headers: 请求头
            timeout: 超时秒数

        Returns:
            包含 status / headers / body 的字典
        """
        return await _do_request("GET", url, headers, None, timeout)

    # ============================================================
    # 工具 3：http_post
    # ============================================================
    @mcp.tool(
        name="http_post",
        description=(
            "发送 HTTP POST 请求。Body 自动序列化为 JSON。"
            "【必用·HTTP POST 专用】"
        ),
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def http_post(
        url: str,
        body: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 30,
    ) -> Dict[str, Any]:
        """
        发送 HTTP POST 请求

        Args:
            url: 请求 URL
            body: 请求体（JSON）
            headers: 请求头
            timeout: 超时秒数

        Returns:
            包含 status / headers / body 的字典
        """
        return await _do_request("POST", url, headers, body, timeout)

    return 3  # 注册的工具数量
