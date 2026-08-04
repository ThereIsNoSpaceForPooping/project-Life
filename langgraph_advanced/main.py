# -*- coding: utf-8 -*-
"""
LangGraph 高级功能演示 - 启动入口

启动 FastAPI 应用，提供完整的 Agent 服务。

使用方法：
    python main.py

或者：
    uvicorn main:app --host 0.0.0.0 --port 8005 --reload
"""

import asyncio
from contextlib import asynccontextmanager
import uvicorn
from app import app
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


async def startup_init():
    """
    启动初始化

    在应用启动时加载 MCP 和 A2A 工具并打印可用工具列表。
    """
    from app.agent.nodes import tool_manager
    from app.agent.mcp.tools_loader import load_mcp_tools, print_available_tools
    from app.agent.a2a.tools_loader import load_a2a_tools

    logger.info("=" * 60)
    logger.info("开始加载外部工具...")
    logger.info("=" * 60)

    # 1. 加载 MCP 工具
    try:
        mcp_tools = await load_mcp_tools()
        tool_manager.set_mcp_tools(mcp_tools)
        logger.info(f"MCP 工具加载完成，共 {len(mcp_tools)} 个")
    except Exception as e:
        logger.warning(f"MCP 工具加载失败: {e}，仅使用本地工具")

    # 2. 加载 A2A 工具
    try:
        a2a_tools = await load_a2a_tools()
        tool_manager.set_a2a_tools(a2a_tools)
        logger.info(f"A2A 工具加载完成，共 {len(a2a_tools)} 个")
    except Exception as e:
        logger.warning(f"A2A 工具加载失败: {e}")

    # 3. 打印所有可用工具
    try:
        await print_available_tools(tool_manager.get_all_tools())
    except Exception as e:
        logger.warning(f"打印工具列表失败: {e}")


@asynccontextmanager
async def lifespan(app):
    """
    FastAPI 现代 lifespan 事件（替代已废弃的 @app.on_event("startup")）

    在应用启动时执行 startup_init() 加载外部工具。
    """
    # ===== startup =====
    await startup_init()
    yield
    # ===== shutdown ===== （暂无需清理）


# 把 lifespan 挂到 app（替换旧的 on_event 装饰器）
app.router.lifespan_context = lifespan


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info(f"启动 {settings.APP_NAME}")
    logger.info(f"版本: 1.0.0")
    logger.info(f"环境: {settings.APP_ENV}")
    logger.info(f"地址: http://{settings.HOST}:{settings.PORT}")
    logger.info(f"文档: http://{settings.HOST}:{settings.PORT}/docs")
    logger.info("=" * 60)

    # 注意：set_mcp_tools / set_a2a_tools 已迁移到 lifespan 内执行，
    # 因为 uvicorn 可能在 asyncio.run() 之后 fork worker 子进程，
    # 子进程需要在自己的事件循环内重新加载工具。
    # 保留 main() 内的 startup_init 调用仅为兼容 debug 场景。
    logger.info("跳过 main() 阶段工具加载，工具将在 lifespan 中加载（避免 fork 后丢失）")
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False,  # 关闭 reload 避免双进程
    )


if __name__ == "__main__":
    main()
