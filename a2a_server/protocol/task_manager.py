# -*- coding: utf-8 -*-
"""
A2A 协议层 - 任务状态机管理

负责：
    - 任务创建、查询、取消
    - 状态转换
    - 内存存储（含可选的 TTL 清理）
"""

import asyncio
import logging
import uuid
from typing import Any, Dict, Optional

from protocol.types import Task, TaskState, TaskStatus, Message

logger: logging.Logger = logging.getLogger("a2a.task_manager")


class TaskManager:
    """
    A2A 任务管理器

    内存版实现（生产环境可替换为 Redis / DB）。
    提供：
        - 任务 CRUD
        - 状态机校验
        - 异步锁保证并发安全
    """

    def __init__(self) -> None:
        self._tasks: Dict[str, Task] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._global_lock: asyncio.Lock = asyncio.Lock()

    def create_task(
        self,
        agent_name: str,
        input_text: str,
        input_parts: list,
        metadata: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> Task:
        """
        创建任务

        初始状态：submitted

        Args:
            agent_name: 目标 Agent
            input_text: 用户文本
            input_parts: 用户消息 parts
            metadata: 客户端元数据
            session_id: 会话 ID

        Returns:
            创建的 Task
        """
        task_id: str = f"task_{uuid.uuid4().hex[:16]}"
        initial_status: TaskStatus = TaskStatus(state=TaskState.SUBMITTED)

        task: Task = Task(
            id=task_id,
            agent_name=agent_name,
            status=initial_status,
            metadata=metadata,
            session_id=session_id,
            input_text=input_text,
            input_parts=input_parts,
        )

        # 记录用户输入
        user_message: Message = Message(
            role="user", parts=input_parts
        )
        task.add_message(user_message)

        self._tasks[task_id] = task
        self._locks[task_id] = asyncio.Lock()

        logger.info(
            "[TaskManager] 创建任务: %s, agent=%s, text='%s...'",
            task_id, agent_name, input_text[:40],
        )
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """
        获取任务
        """
        return self._tasks.get(task_id)

    def cancel_task(self, task_id: str) -> bool:
        """
        取消任务

        Returns:
            是否成功取消
        """
        task: Optional[Task] = self._tasks.get(task_id)
        if task is None:
            return False
        if task.is_terminal():
            return False

        task.set_state(TaskState.CANCELED)
        logger.info("[TaskManager] 取消任务: %s", task_id)
        return True

    def size(self) -> int:
        """任务总数"""
        return len(self._tasks)

    def get_lock(self, task_id: str) -> Optional[asyncio.Lock]:
        """获取任务锁（用于并发安全）"""
        return self._locks.get(task_id)
