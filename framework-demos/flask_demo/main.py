# -*- coding: utf-8 -*-
"""
Flask Demo - 应用启动入口

启动方式：
  python main.py

访问地址：
  - API: http://localhost:8003
"""

from app import create_app

# 创建应用实例
app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8003, debug=True)
