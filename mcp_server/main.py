# -*- coding: utf-8 -*-
"""
MCP Server - 真实 MCP 协议实现

基于 Anthropic 官方 MCP（Model Context Protocol）Python SDK 实现，
符合 MCP 规范 2025-03-26。

官方规范：https://modelcontextprotocol.io
官方 SDK：https://github.com/modelcontextprotocol/python-sdk

特性：
    - 传输层：Streamable HTTP（推荐） + stdio
    - 协议：JSON-RPC 2.0
    - 能力：tools / resources / prompts
    - 工具数量：13 个（file / db / http / code）

运行方式：
    # Streamable HTTP 模式（推荐，端口 8001）
    python main.py

    # stdio 模式（用于 Claude Desktop 等本地客户端）
    python main.py --stdio
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# ============================================================
# 路径与环境配置
# ============================================================
# 将当前目录加入 Python 路径，确保 tools 包可被导入
BASE_DIR: Path = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# 加载 .env 环境变量
from dotenv import load_dotenv

load_dotenv(BASE_DIR / ".env")

# ============================================================
# 日志配置
# ============================================================
# 使用统一格式：时间 | 级别 | 模块 | 消息
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)-7s | %(name)-20s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger: logging.Logger = logging.getLogger("mcp_server")

# ============================================================
# 尝试导入官方 MCP SDK
# ============================================================
# 官方 SDK 路径：mcp.server.fastmcp.FastMCP
# 如果未安装，提供清晰的错误提示
try:
    from mcp.server import Server
    from mcp.server.fastmcp import FastMCP
    from mcp.server.stdio import stdio_server
    from mcp.types import (
        CallToolRequest,
        ListToolsRequest,
        TextContent,
    )

    MCP_SDK_AVAILABLE: bool = True
    logger.info("[启动] 已加载官方 MCP SDK (mcp.server.fastmcp.FastMCP)")
except ImportError as exc:  # pragma: no cover
    MCP_SDK_AVAILABLE = False
    logger.error(
        "[启动] 未找到官方 MCP SDK: %s\n"
        "请执行: pip install mcp[cli]>=1.0.0\n"
        "安装地址: https://github.com/modelcontextprotocol/python-sdk",
        exc,
    )
    raise SystemExit(1) from exc

# ============================================================
# 业务模块导入
# ============================================================
# 配置
from config import Config

# 工具实现（四个领域）
from tools.file_tools import register_file_tools
from tools.db_tools import register_db_tools
from tools.http_tools import register_http_tools
from tools.code_tools import register_code_tools


# ============================================================
# MCP Server 实例
# ============================================================
# FastMCP 是官方推荐的 Server 封装：
#   - 内部使用 mcp.server.Server（完整协议实现）
#   - 自动注册 tool 装饰器
#   - 同时支持 Streamable HTTP / SSE / stdio 三种传输
# 配置说明：
#   - instructions：用于在 initialize 阶段返回给客户端
#   - host/port：Streamable HTTP 监听地址
MCP_SERVER_NAME: str = os.getenv("MCP_SERVER_NAME", "project-life-mcp")
MCP_SERVER_HOST: str = os.getenv("MCP_SERVER_HOST", Config.HOST)
MCP_SERVER_PORT: int = int(os.getenv("MCP_SERVER_PORT", str(Config.PORT)))

# 创建 FastMCP 实例
mcp: FastMCP = FastMCP(
    name=MCP_SERVER_NAME,
    instructions=(
        "Project-Life MCP Server 提供 13 个工具，"
        "涵盖文件操作、数据库查询、HTTP 请求、Python 代码执行。"
        "所有工具遵循 JSON-RPC 2.0 协议，可通过 Streamable HTTP 接入。"
    ),
    host=MCP_SERVER_HOST,
    port=MCP_SERVER_PORT,
)


# ============================================================
# 注册所有工具
# ============================================================
# 领域一：文件操作（4 个）
#   file_read / file_write / file_list / file_delete
# 领域二：数据库操作（4 个）
#   db_query / db_execute / db_tables / db_schema
# 领域三：HTTP 请求（3 个）
#   http_request / http_get / http_post
# 领域四：代码执行（2 个）
#   code_execute / code_evaluate
def _register_all_tools() -> int:
    """
    注册所有业务工具到 FastMCP 实例

    各领域工具在自己的模块中通过 @mcp.tool() 装饰器注册，
    此函数仅用于触发模块加载并返回工具数量。

    Returns:
        注册的工具数量
    """
    file_count: int = register_file_tools(mcp)
    db_count: int = register_db_tools(mcp)
    http_count: int = register_http_tools(mcp)
    code_count: int = register_code_tools(mcp)

    total: int = file_count + db_count + http_count + code_count
    logger.info(
        "[注册] 工具已全部注册: file=%d, db=%d, http=%d, code=%d, total=%d",
        file_count,
        db_count,
        http_count,
        code_count,
        total,
    )
    return total


# ============================================================
# 启动入口
# ============================================================
def _print_banner(tool_count: int, transport: str) -> None:
    """
    打印启动横幅

    Args:
        tool_count: 已注册工具数量
        transport: 传输模式（http / stdio）
    """
    print(
        f"""
╔═══════════════════════════════════════════════════════════╗
║           MCP Server (Anthropic MCP 协议)                ║
╠═══════════════════════════════════════════════════════════╣
║  传输模式: {transport:<44} ║
║  监听地址: {f"{MCP_SERVER_HOST}:{MCP_SERVER_PORT}":<44} ║
║  工具数量: {tool_count:<44} ║
║  协议版本: 2025-03-26 (JSON-RPC 2.0)                      ║
╠═══════════════════════════════════════════════════════════╣
║  工具分类:                                                ║
║   • file_read / file_write / file_list / file_delete      ║
║   • db_query / db_execute / db_tables / db_schema         ║
║   • http_request / http_get / http_post                   ║
║   • code_execute / code_evaluate                          ║
╠═══════════════════════════════════════════════════════════╣
║  客户端接入:                                              ║
║   Streamable HTTP  → http://{MCP_SERVER_HOST}:{MCP_SERVER_PORT}/mcp  ║
║   健康检查        → http://{MCP_SERVER_HOST}:{MCP_SERVER_PORT}/health ║
╚═══════════════════════════════════════════════════════════╝
"""
    )


async def run_http() -> None:
    """
    以 Streamable HTTP 模式启动 MCP Server

    Streamable HTTP 是 MCP 2025-03-26 规范推荐的传输方式，
    单端点 /mcp 同时支持 GET（建立 SSE 流）和 POST（发送请求）。
    """
    # 注册业务工具
    tool_count: int = _register_all_tools()

    # 打印启动横幅
    _print_banner(tool_count, "Streamable HTTP")

    # 添加自定义健康检查路由
    # FastMCP 内部是 Starlette 应用，可直接挂载路由
    try:
        from starlette.responses import JSONResponse
        from starlette.routing import Route

        async def health(_request):  # noqa: ANN001
            """健康检查端点（HTTP / 非 MCP 协议）"""
            return JSONResponse(
                {
                    "status": "ok",
                    "service": MCP_SERVER_NAME,
                    "protocol": "MCP",
                    "version": "2025-03-26",
                    "tools": tool_count,
                }
            )

        # 在内部 Starlette 应用上添加路由
        if hasattr(mcp, "_app") and mcp._app is not None:
            mcp._app.router.routes.append(Route("/health", endpoint=health))
            logger.info("[启动] 已挂载 /health 健康检查路由")
    except Exception as exc:  # pragma: no cover
        logger.warning("[启动] 挂载 /health 失败（不影响 MCP 协议）: %s", exc)

    # 启动 Streamable HTTP 服务
    # run() 内部会使用 uvicorn 启动 Starlette 应用
    logger.info(
        "[启动] Streamable HTTP 监听: http://%s:%d/mcp",
        MCP_SERVER_HOST,
        MCP_SERVER_PORT,
    )
    await mcp.run(transport="streamable-http")


async def run_stdio() -> None:
    """
    以 stdio 模式启动 MCP Server

    stdio 模式用于本地进程通信（如 Claude Desktop），
    通过 stdin/stdout 交换 JSON-RPC 消息。
    """
    # 注册业务工具
    tool_count: int = _register_all_tools()
    _print_banner(tool_count, "stdio")

    logger.info("[启动] stdio 模式启动（通过 stdin/stdout 通信）")

    # stdio_server 是官方 SDK 提供的异步上下文管理器
    async with stdio_server() as (read_stream, write_stream):
        # 获取底层 Server 实例并运行
        # mcp._server 是 FastMCP 内部的 Server 实例
        server: Server = mcp._server  # type: ignore[attr-defined]
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    """
    主入口：解析命令行参数并选择传输模式

    支持：
        python main.py            # 默认 Streamable HTTP
        python main.py --stdio    # stdio 模式
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="MCP Server - 真实 Anthropic MCP 协议实现"
    )
    parser.add_argument(
        "--stdio",
        action="store_true",
        help="使用 stdio 传输（用于本地 MCP 客户端）",
    )
    args: argparse.Namespace = parser.parse_args()

    try:
        if args.stdio:
            asyncio.run(run_stdio())
        else:
            asyncio.run(run_http())
    except KeyboardInterrupt:  # pragma: no cover
        logger.info("[关闭] 用户中断，正在退出...")
    except Exception as exc:  # pragma: no cover
        logger.exception("[异常] MCP Server 运行失败: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
