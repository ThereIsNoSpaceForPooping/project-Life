"""手动启动脚本（无 reload，方便调试）"""
import uvicorn
from app import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8005, log_level="info")
