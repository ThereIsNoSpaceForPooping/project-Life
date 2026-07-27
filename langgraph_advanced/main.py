# -*- coding: utf-8 -*-
"""
LangGraph 高级功能演示 - 启动入口

启动 FastAPI 应用，提供完整的 Agent 服务。

使用方法：
    python main.py
    
或者：
    uvicorn main:app --host 0.0.0.0 --port 8005 --reload
"""

import uvicorn
from app import app
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info(f"启动 {settings.APP_NAME}")
    logger.info(f"版本: 1.0.0")
    logger.info(f"环境: {settings.APP_ENV}")
    logger.info(f"地址: http://{settings.HOST}:{settings.PORT}")
    logger.info(f"文档: http://{settings.HOST}:{settings.PORT}/docs")
    logger.info("=" * 60)
    
    # 启动服务
    uvicorn.run(
        app,
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.APP_ENV == "development"
    )


if __name__ == "__main__":
    main()
