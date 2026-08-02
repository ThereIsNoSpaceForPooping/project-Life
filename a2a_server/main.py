# -*- coding: utf-8 -*-
"""
A2A Server - 主入口

提供 A2A 协议的 HTTP 服务端。
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional
import uuid
from datetime import datetime

from config import Config
from agents.registry import agent_registry

# 创建 FastAPI 应用
app = FastAPI(
    title="A2A Server",
    description="Agent-to-Agent Protocol Server - 提供多 Agent 协作能力",
    version="1.0.0"
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# 任务存储（内存）
# ============================================================

class TaskStore:
    """任务存储"""
    
    def __init__(self):
        self._tasks = {}
    
    def create_task(self, agent_name: str, input_data: dict) -> dict:
        """创建任务"""
        task_id = str(uuid.uuid4())
        task = {
            "id": task_id,
            "agent_name": agent_name,
            "input_data": input_data,
            "status": "pending",
            "result": None,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        self._tasks[task_id] = task
        return task
    
    def get_task(self, task_id: str) -> Optional[dict]:
        """获取任务"""
        return self._tasks.get(task_id)
    
    def update_task(self, task_id: str, status: str, result: Any = None):
        """更新任务"""
        task = self._tasks.get(task_id)
        if task:
            task["status"] = status
            task["result"] = result
            task["updated_at"] = datetime.now().isoformat()
    
    def list_tasks(self, limit: int = 100) -> list:
        """列出任务"""
        tasks = list(self._tasks.values())
        tasks.sort(key=lambda x: x["created_at"], reverse=True)
        return tasks[:limit]


# 全局任务存储
task_store = TaskStore()


# ============================================================
# 请求/响应模型
# ============================================================

class TaskRequest(BaseModel):
    """任务请求"""
    agent_name: str
    input_data: Dict[str, Any]


class TaskResponse(BaseModel):
    """任务响应"""
    task_id: str
    status: str
    result: Optional[Any] = None


class AgentInfo(BaseModel):
    """Agent 信息"""
    name: str
    description: str
    capabilities: list[str]


# ============================================================
# API 接口
# ============================================================

@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "service": "a2a_server"}


@app.get("/.well-known/agent.json")
async def agent_card():
    """
    Agent Card - 服务发现
    
    返回当前服务提供的 Agent 列表。
    """
    agents = agent_registry.get_all_agents()
    
    return {
        "name": "A2A Server",
        "version": "1.0.0",
        "description": "多 Agent 协作服务",
        "agents": agents
    }


@app.get("/a2a/agents", response_model=list[AgentInfo])
async def list_agents():
    """
    列出所有可用 Agent
    
    Returns:
        Agent 列表
    """
    agents = agent_registry.get_all_agents()
    
    return [
        AgentInfo(
            name=agent["name"],
            description=agent["description"],
            capabilities=agent["capabilities"]
        )
        for agent in agents
    ]


@app.post("/a2a/tasks", response_model=TaskResponse)
async def create_task(request: TaskRequest):
    """
    创建任务
    
    Args:
        request: 任务请求
    
    Returns:
        任务响应
    """
    # 检查 Agent 是否存在
    agent = agent_registry.get_agent(request.agent_name)
    if not agent:
        raise HTTPException(
            status_code=404,
            detail=f"Agent 不存在: {request.agent_name}"
        )
    
    # 创建任务
    task = task_store.create_task(request.agent_name, request.input_data)
    
    # 执行任务
    task_store.update_task(task["id"], "running")
    
    try:
        result = await agent_registry.process_task(
            request.agent_name,
            request.input_data
        )
        
        # 检查是否有错误
        if isinstance(result, dict) and "error" in result:
            task_store.update_task(task["id"], "failed", result)
            return TaskResponse(
                task_id=task["id"],
                status="failed",
                result=result
            )
        
        task_store.update_task(task["id"], "completed", result)
        
        return TaskResponse(
            task_id=task["id"],
            status="completed",
            result=result
        )
    
    except Exception as e:
        task_store.update_task(task["id"], "failed", {"error": str(e)})
        
        return TaskResponse(
            task_id=task["id"],
            status="failed",
            result={"error": str(e)}
        )


@app.get("/a2a/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    """
    获取任务状态
    
    Args:
        task_id: 任务 ID
    
    Returns:
        任务状态
    """
    task = task_store.get_task(task_id)
    
    if not task:
        raise HTTPException(
            status_code=404,
            detail=f"任务不存在: {task_id}"
        )
    
    return TaskResponse(
        task_id=task["id"],
        status=task["status"],
        result=task["result"]
    )


@app.get("/a2a/tasks")
async def list_tasks(limit: int = 100):
    """
    列出所有任务
    
    Args:
        limit: 最大返回数量
    
    Returns:
        任务列表
    """
    tasks = task_store.list_tasks(limit)
    
    return {
        "tasks": tasks,
        "total": len(tasks)
    }


# ============================================================
# 启动入口
# ============================================================

if __name__ == "__main__":
    import uvicorn
    
    print(f"""
╔═══════════════════════════════════════════════════════════╗
║                    A2A Server                             ║
╠═══════════════════════════════════════════════════════════╣
║  端口: {Config.PORT}                                        ║
║  Agent 数量: 4                                            ║
║                                                           ║
║  可用 Agent:                                              ║
║  - researcher: 研究助手（信息搜索和整理）                   ║
║  - coder: 编码助手（代码生成和审查）                        ║
║  - translator: 翻译助手（多语言翻译）                       ║
║  - analyzer: 分析助手（数据分析和洞察）                     ║
╚═══════════════════════════════════════════════════════════╝
    """)
    
    uvicorn.run(
        app,
        host=Config.HOST,
        port=Config.PORT
    )
