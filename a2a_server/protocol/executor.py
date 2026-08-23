# -*- coding: utf-8 -*-
"""
A2A 协议层 - 任务执行器

负责协调 Agent 注册表与任务状态机：
    - submitted → working
    - working → completed / failed / input-required
    - 工作过程中产生 artifact 和 message，实时通过 EventBroker 推送
"""

import asyncio
import logging
import traceback
from typing import Any, Dict, List, Optional

from protocol.types import (
    Task,
    TaskState,
    Message,
    Artifact,
    TextPart,
)
from protocol.task_manager import TaskManager
from protocol.streaming import EventBroker
from agents.base import BaseAgent

logger: logging.Logger = logging.getLogger("a2a.executor")


class TaskExecutor:
    """
    任务执行器

    不做实际的业务逻辑（那是 Agent 的事）。
    它的职责：
        1. 状态机推进
        2. 异常捕获与状态转换
        3. 事件广播
    """

    def __init__(
        self,
        task_manager: TaskManager,
        event_broker: EventBroker,
        agent_registry: Any,  # AgentRegistry, 避免循环引用
    ) -> None:
        self.task_manager: TaskManager = task_manager
        self.event_broker: EventBroker = event_broker
        self.agent_registry: Any = agent_registry

    async def execute(self, task: Task, user_text: str) -> None:
        """
        执行任务

        Args:
            task: 任务对象（mutated in place）
            user_text: 用户输入文本
        """
        # 1. submitted → working
        self._publish_status(task, TaskState.WORKING)
        task.set_state(TaskState.WORKING)

        try:
            # 2. 查找 Agent
            agent: Optional[BaseAgent] = self.agent_registry.get_agent(
                task.agent_name
            )
            if agent is None:
                raise RuntimeError(
                    f"未找到 Agent: {task.agent_name}"
                )

            logger.info(
                "[Executor] 任务 %s 路由到 %s",
                task.id, agent.name,
            )

            # 3. 调用 Agent
            result: Dict[str, Any] = await agent.run(
                user_text=user_text,
                history=[m.to_dict() for m in task.messages],
            )

            # 4. 处理结果
            output_text: str = result.get("output", "")
            artifacts: List[Dict[str, Any]] = result.get("artifacts", [])

            # 推送中间消息（思考过程）
            intermediate: List[Dict[str, Any]] = result.get("intermediate", [])
            for item in intermediate:
                if item.get("type") == "message":
                    self._publish_message(
                        task,
                        item.get("role", "agent"),
                        item.get("text", ""),
                    )

            # 推送最终回复
            if output_text:
                self._publish_message(task, "agent", output_text)
                agent_message: Message = Message(
                    role="agent",
                    parts=[{"type": "text", "text": output_text}],
                )
                task.add_message(agent_message)

            # 推送 artifacts
            for art in artifacts:
                artifact: Artifact = Artifact(
                    name=art.get("name", "output"),
                    parts=art.get("parts", []),
                    description=art.get("description"),
                )
                task.add_artifact(artifact)
                self._publish_artifact(task, artifact)

            # 5. working → completed
            self._publish_status(task, TaskState.COMPLETED)
            task.set_state(TaskState.COMPLETED)
            self._publish_end(task)

            logger.info(
                "[Executor] 任务 %s 完成 (output: %d 字符, %d artifacts)",
                task.id, len(output_text), len(task.artifacts),
            )

        except Exception as exc:
            error_msg: str = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
            logger.exception("[Executor] 任务 %s 失败: %s", task.id, exc)
            self._publish_status(task, TaskState.FAILED, message=str(exc))
            task.set_state(TaskState.FAILED, error=error_msg)
            self._publish_end(task)

    # ============================================================
    # 事件发布辅助
    # ============================================================
    def _publish_status(
        self,
        task: Task,
        state: TaskState,
        message: Optional[str] = None,
    ) -> None:
        """发布状态变更事件"""
        event: Dict[str, Any] = {
            "type": "status",
            "taskId": task.id,
            "state": state.value,
        }
        if message:
            event["message"] = message
        self.event_broker.publish(task.id, event)

    def _publish_message(
        self,
        task: Task,
        role: str,
        text: str,
    ) -> None:
        """发布消息事件"""
        self.event_broker.publish(
            task.id,
            {
                "type": "message",
                "taskId": task.id,
                "role": role,
                "text": text,
            },
        )

    def _publish_artifact(self, task: Task, artifact: Artifact) -> None:
        """发布产物事件"""
        self.event_broker.publish(
            task.id,
            {
                "type": "artifact",
                "taskId": task.id,
                "artifact": artifact.to_dict(),
            },
        )

    def _publish_end(self, task: Task) -> None:
        """发布流结束事件"""
        self.event_broker.publish(
            task.id, {"type": "end", "taskId": task.id}
        )
