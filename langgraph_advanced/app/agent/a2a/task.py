# -*- coding: utf-8 -*-
"""
A2A Task 实现

Task 是 A2A 协议中的任务管理模块。
当一个 Agent 需要另一个 Agent 帮助时，会创建一个 Task。

学习要点：
1. Task 是 Agent 间协作的基本单位
2. Task 有完整的生命周期（创建 → 执行 → 完成/失败）
3. Task 包含输入、输出、状态、历史记录
4. 支持异步执行和状态查询

架构图：
    Agent A                          Agent B
       │                                │
       │── 创建 Task ─────────────────▶│
       │   (Task ID: task-123)          │
       │                                │── 执行任务
       │── 查询状态 ──────────────────▶│
       │◀── 返回状态: "执行中" ─────────│
       │                                │── 继续执行
       │── 查询状态 ──────────────────▶│
       │◀── 返回结果 ──────────────────│
       │                                │
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.core.logging import get_logger

logger = get_logger(__name__)


# ============================================================
# Task 状态枚举
# ============================================================
class TaskStatus(str, Enum):
    """
    Task 状态枚举
    
    状态流转：
        PENDING → RUNNING → COMPLETED
                    ↓
                 FAILED
                    ↓
                 CANCELLED
    """
    PENDING = "pending"         # 待执行
    RUNNING = "running"         # 执行中
    COMPLETED = "completed"     # 已完成
    FAILED = "failed"           # 执行失败
    CANCELLED = "cancelled"     # 已取消


# ============================================================
# Task 定义
# ============================================================
class Task(BaseModel):
    """
    Task - Agent 间的任务
    
    包含任务的完整信息：
    - 基本信息（ID、名称、描述）
    - 输入参数
    - 输出结果
    - 状态和进度
    - 时间戳
    - 错误信息
    
    属性：
        id: 任务唯一标识
        name: 任务名称
        description: 任务描述
        input_data: 输入数据
        output_data: 输出数据
        status: 任务状态
        progress: 进度（0-100）
        created_at: 创建时间
        started_at: 开始时间
        completed_at: 完成时间
        error: 错误信息
        metadata: 额外元数据
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="任务 ID")
    name: str = Field(..., description="任务名称")
    description: str = Field(default="", description="任务描述")
    input_data: Dict[str, Any] = Field(default_factory=dict, description="输入数据")
    output_data: Dict[str, Any] = Field(default_factory=dict, description="输出数据")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="任务状态")
    progress: int = Field(default=0, ge=0, le=100, description="进度（0-100）")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    started_at: Optional[datetime] = Field(default=None, description="开始时间")
    completed_at: Optional[datetime] = Field(default=None, description="完成时间")
    error: Optional[str] = Field(default=None, description="错误信息")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="额外元数据")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式
        
        Returns:
            Dict: Task 的字典表示
        """
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "inputData": self.input_data,
            "outputData": self.output_data,
            "status": self.status.value,
            "progress": self.progress,
            "createdAt": self.created_at.isoformat(),
            "startedAt": self.started_at.isoformat() if self.started_at else None,
            "completedAt": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
            "metadata": self.metadata,
        }


# ============================================================
# Task Manager - 任务管理器
# ============================================================
class TaskManager:
    """
    Task Manager - 管理所有 Task
    
    职责：
    1. 创建和管理 Task
    2. 更新 Task 状态
    3. 查询 Task 状态
    4. 清理完成的 Task
    """
    
    def __init__(self):
        """初始化任务管理器"""
        self._tasks: Dict[str, Task] = {}
        logger.info("Task Manager 初始化")
    
    def create_task(
        self,
        name: str,
        description: str = "",
        input_data: Dict[str, Any] = None,
        metadata: Dict[str, Any] = None
    ) -> Task:
        """
        创建新任务
        
        Args:
            name: 任务名称
            description: 任务描述
            input_data: 输入数据
            metadata: 额外元数据
        
        Returns:
            Task: 创建的任务实例
        """
        task = Task(
            name=name,
            description=description,
            input_data=input_data or {},
            metadata=metadata or {}
        )
        
        self._tasks[task.id] = task
        logger.info(f"创建任务: {task.name} (ID: {task.id})")
        
        return task
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """
        获取任务
        
        Args:
            task_id: 任务 ID
        
        Returns:
            Task: 任务实例，如果不存在则返回 None
        """
        return self._tasks.get(task_id)
    
    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        progress: int = None,
        output_data: Dict[str, Any] = None,
        error: str = None
    ) -> Optional[Task]:
        """
        更新任务状态
        
        Args:
            task_id: 任务 ID
            status: 新状态
            progress: 进度（0-100）
            output_data: 输出数据
            error: 错误信息
        
        Returns:
            Task: 更新后的任务实例
        """
        task = self._tasks.get(task_id)
        if not task:
            logger.warning(f"任务不存在: {task_id}")
            return None
        
        # 更新状态
        task.status = status
        
        # 更新时间戳
        if status == TaskStatus.RUNNING and not task.started_at:
            task.started_at = datetime.now()
        elif status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            task.completed_at = datetime.now()
        
        # 更新进度
        if progress is not None:
            task.progress = progress
        
        # 更新输出数据
        if output_data is not None:
            task.output_data = output_data
        
        # 更新错误信息
        if error is not None:
            task.error = error
        
        logger.info(f"更新任务状态: {task.name} → {status.value}")
        return task
    
    def list_tasks(
        self,
        status: TaskStatus = None,
        limit: int = 100
    ) -> List[Task]:
        """
        列出任务
        
        Args:
            status: 按状态过滤（可选）
            limit: 最大返回数量
        
        Returns:
            List[Task]: 任务列表
        """
        tasks = list(self._tasks.values())
        
        # 按状态过滤
        if status:
            tasks = [t for t in tasks if t.status == status]
        
        # 按创建时间倒序
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        
        # 限制数量
        return tasks[:limit]
    
    def cancel_task(self, task_id: str) -> Optional[Task]:
        """
        取消任务
        
        Args:
            task_id: 任务 ID
        
        Returns:
            Task: 取消后的任务实例
        """
        task = self._tasks.get(task_id)
        if not task:
            logger.warning(f"任务不存在: {task_id}")
            return None
        
        if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            logger.warning(f"任务已结束，无法取消: {task_id}")
            return task
        
        return self.update_task_status(task_id, TaskStatus.CANCELLED)
    
    def cleanup_completed_tasks(self, max_age_hours: int = 24) -> int:
        """
        清理已完成的任务
        
        Args:
            max_age_hours: 最大保留时间（小时）
        
        Returns:
            int: 清理的任务数量
        """
        now = datetime.now()
        to_remove = []
        
        for task_id, task in self._tasks.items():
            if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                if task.completed_at:
                    age_hours = (now - task.completed_at).total_seconds() / 3600
                    if age_hours > max_age_hours:
                        to_remove.append(task_id)
        
        for task_id in to_remove:
            del self._tasks[task_id]
        
        logger.info(f"清理 {len(to_remove)} 个已完成任务")
        return len(to_remove)


# 全局任务管理器
task_manager = TaskManager()
