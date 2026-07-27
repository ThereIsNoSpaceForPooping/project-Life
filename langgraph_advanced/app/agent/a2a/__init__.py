# -*- coding: utf-8 -*-
"""
A2A 模块初始化

A2A（Agent-to-Agent）是 Google 推出的开放协议，
用于标准化 AI Agent 之间的通信和协作。

本模块包含：
- agent_card.py: Agent Card 定义（Agent 的"名片"）
- task.py: Task 管理（任务生命周期）
- message.py: Message 通信（Agent 间消息传递）
- protocol.py: A2A 协议实现（核心协调器）

架构图：
    ┌─────────────────────────────────────────────────────────────┐
    │                        A2A 架构                              │
    ├─────────────────────────────────────────────────────────────┤
    │                                                              │
    │   ┌──────────┐     Agent Card      ┌──────────┐            │
    │   │  Agent A  │ ◀────────────────▶ │  Agent B  │            │
    │   │(协调者)   │     Message/Task    │(研究助手) │            │
    │   └────┬─────┘                     └──────────┘            │
    │        │                                                     │
    │        │ Agent Card      ┌──────────┐                      │
    │        └────────────────▶ │  Agent C  │                      │
    │          Message/Task     │(编码助手) │                      │
    │                           └──────────┘                      │
    │                                │                             │
    │                                │ Agent Card  ┌──────────┐  │
    │                                └────────────▶│  Agent D  │  │
    │                                  Message/Task │(总结助手) │  │
    │                                               └──────────┘  │
    │                                                              │
    └─────────────────────────────────────────────────────────────┘

使用示例：
    # 1. 发现 Agent
    agents = a2a_protocol.discover_agents("search")
    
    # 2. 创建任务
    task = a2a_protocol.create_task("研究助手", "web_search", {"query": "Python"})
    
    # 3. 执行任务
    result = await a2a_protocol.execute_task(task.id)
    
    # 4. 查询状态
    status = a2a_protocol.get_task_status(task.id)
"""

from app.agent.a2a.agent_card import (
    AgentCapability,
    AgentCard,
    AgentCardRegistry,
    agent_card_registry,
    RESEARCH_AGENT_CARD,
    CODER_AGENT_CARD,
    SUMMARIZER_AGENT_CARD,
)

from app.agent.a2a.task import (
    Task,
    TaskStatus,
    TaskManager,
    task_manager,
)

from app.agent.a2a.message import (
    Message,
    MessageType,
    MessageFactory,
    MessageHistory,
    message_history,
)

from app.agent.a2a.protocol import (
    A2AProtocol,
    a2a_protocol,
)

__all__ = [
    # Agent Card
    "AgentCapability",
    "AgentCard",
    "AgentCardRegistry",
    "agent_card_registry",
    "RESEARCH_AGENT_CARD",
    "CODER_AGENT_CARD",
    "SUMMARIZER_AGENT_CARD",
    
    # Task
    "Task",
    "TaskStatus",
    "TaskManager",
    "task_manager",
    
    # Message
    "Message",
    "MessageType",
    "MessageFactory",
    "MessageHistory",
    "message_history",
    
    # Protocol
    "A2AProtocol",
    "a2a_protocol",
]
