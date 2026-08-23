# -*- coding: utf-8 -*-
"""
A2A 协议层 - 事件代理

提供基于 asyncio 的发布订阅机制。
每个 task_id 维护一个事件队列，支持多订阅者。
"""

import asyncio
import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional

logger: logging.Logger = logging.getLogger("a2a.event_broker")


class EventBroker:
    """
    异步事件代理

    用于：
        - SSE 流式响应推送
        - 多订阅者支持（一个任务可被多个客户端订阅）
        - 任务级别隔离
    """

    def __init__(self) -> None:
        # task_id → {subscriber_id → asyncio.Queue}
        self._subscribers: Dict[str, Dict[str, asyncio.Queue]] = defaultdict(dict)
        self._lock: asyncio.Lock = asyncio.Lock()

    def subscribe(self, task_id: str, subscriber_id: str) -> None:
        """
        订阅任务事件

        Args:
            task_id: 任务 ID
            subscriber_id: 订阅者 ID（客户端唯一标识）
        """
        if subscriber_id not in self._subscribers[task_id]:
            self._subscribers[task_id][subscriber_id] = asyncio.Queue()
            logger.debug(
                "[EventBroker] 订阅: task=%s, sub=%s",
                task_id, subscriber_id,
            )

    def unsubscribe(self, task_id: str, subscriber_id: str) -> None:
        """取消订阅"""
        if task_id in self._subscribers:
            self._subscribers[task_id].pop(subscriber_id, None)
            if not self._subscribers[task_id]:
                self._subscribers.pop(task_id, None)

    def publish(self, task_id: str, event: Dict[str, Any]) -> None:
        """
        发布事件给所有订阅者

        Args:
            task_id: 任务 ID
            event: 事件字典
        """
        subscribers: Dict[str, asyncio.Queue] = self._subscribers.get(
            task_id, {}
        )
        for queue in subscribers.values():
            # 非阻塞放入（避免慢消费者阻塞）
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(
                    "[EventBroker] 队列已满，丢弃事件: task=%s",
                    task_id,
                )

    async def get_event(
        self,
        task_id: str,
        subscriber_id: str,
        timeout: float = 1.0,
    ) -> Optional[Dict[str, Any]]:
        """
        拉取一个事件

        Args:
            task_id: 任务 ID
            subscriber_id: 订阅者 ID
            timeout: 超时秒数

        Returns:
            事件字典，超时返回 None
        """
        queue: Optional[asyncio.Queue] = self._subscribers.get(
            task_id, {}
        ).get(subscriber_id)
        if queue is None:
            return None
        try:
            event: Dict[str, Any] = await asyncio.wait_for(
                queue.get(), timeout=timeout
            )
            return event
        except asyncio.TimeoutError:
            return None
        except Exception as exc:  # pragma: no cover
            logger.warning("[EventBroker] 拉取事件异常: %s", exc)
            return None
