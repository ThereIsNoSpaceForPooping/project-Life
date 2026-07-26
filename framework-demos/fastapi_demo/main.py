# -*- coding: utf-8 -*-
"""
FastAPI Demo - 应用启动入口

启动方式：
  python main.py

访问地址：
  - API: http://localhost:8001
  - Swagger UI: http://localhost:8001/docs
  - ReDoc: http://localhost:8001/redoc
"""

import uvicorn
from app import create_app

# 创建应用实例
app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )
