# -*- coding: utf-8 -*-
"""
A2A Protocol 实现

A2A Protocol 是 Agent-to-Agent 通信协议的核心。
它定义了 Agent 之间如何发现、通信和协作。

学习要点：
1. A2A 协议包含：发现 → 通信 → 协作
2. Agent 通过 Agent Card 发现彼此
3. 通过 Message 进行通信
4. 通过 Task 管理协作任务
5. 支持同步和异步两种模式

架构图：
    ┌─────────────────────────────────────────────────────────────┐
    │                      A2A 协议流程                            │
    ├─────────────────────────────────────────────────────────────┤
    │                                                              │
    │  1. 发现阶段                                                 │
    │     Agent A → 获取 Agent Card → Agent B                     │
    │                                                              │
    │  2. 通信阶段                                                 │
    │     Agent A → 发送 Task → Agent B                           │
    │     Agent B → 返回结果 → Agent A                            │
    │                                                              │
    │  3. 协作阶段                                                 │
    │     Agent A → 发送后续任务 → Agent B                        │
    │     Agent B → 返回最终结果 → Agent A                        │
    │                                                              │
    └─────────────────────────────────────────────────────────────┘
"""

import asyncio
from typing import Any, Dict, List, Optional

from app.agent.a2a.agent_card import AgentCard, agent_card_registry
from app.agent.a2a.task import Task, TaskStatus, task_manager
from app.agent.a2a.message import (
    Message, MessageType, MessageFactory, message_history
)
from app.agent.nodes import get_llm
from app.agent.tools import web_search, search_knowledge, calculate
from app.core.logging import get_logger

logger = get_logger(__name__)


# ============================================================
# A2A Protocol 类
# ============================================================
class A2AProtocol:
    """
    A2A Protocol - Agent-to-Agent 通信协议
    
    职责：
    1. 管理 Agent 注册和发现
    2. 处理 Agent 间的消息路由
    3. 管理任务生命周期
    4. 执行 Agent 的具体能力
    
    使用示例：
        protocol = A2AProtocol()
        
        # 发现 Agent
        agents = protocol.discover_agents("search")
        
        # 创建任务
        task = protocol.create_task("研究助手", "web_search", {"query": "Python"})
        
        # 执行任务
        result = await protocol.execute_task(task.id)
    """
    
    def __init__(self, agent_name: str = "coordinator"):
        """
        初始化 A2A 协议
        
        Args:
            agent_name: 当前 Agent 名称
        """
        self.agent_name = agent_name
        self._agent_handlers: Dict[str, callable] = {}
        
        # 注册默认的 Agent 处理器
        self._register_default_handlers()
        
        logger.info(f"A2A Protocol 初始化: {agent_name}")
    
    def _register_default_handlers(self):
        """注册默认的 Agent 处理器"""
        self._agent_handlers["研究助手"] = self._handle_research_agent
        self._agent_handlers["编码助手"] = self._handle_coder_agent
        self._agent_handlers["总结助手"] = self._handle_summarizer_agent
    
    # ============================================================
    # 发现功能
    # ============================================================
    def discover_agents(self, capability: str = None) -> List[AgentCard]:
        """
        发现 Agent
        
        Args:
            capability: 按能力过滤（可选）
        
        Returns:
            List[AgentCard]: Agent Card 列表
        
        使用示例：
            # 发现所有 Agent
            agents = protocol.discover_agents()
            
            # 发现具有搜索能力的 Agent
            agents = protocol.discover_agents("search")
        """
        if capability:
            return agent_card_registry.discover(capability)
        return agent_card_registry.list_agents()
    
    def get_agent_card(self, agent_name: str) -> Optional[AgentCard]:
        """
        获取指定 Agent 的 Card
        
        Args:
            agent_name: Agent 名称
        
        Returns:
            AgentCard: Agent Card 实例
        """
        return agent_card_registry.get(agent_name)
    
    # ============================================================
    # 任务管理
    # ============================================================
    def create_task(
        self,
        target_agent: str,
        capability: str,
        input_data: Dict[str, Any]
    ) -> Task:
        """
        创建任务
        
        Args:
            target_agent: 目标 Agent 名称
            capability: 要调用的能力
            input_data: 输入数据
        
        Returns:
            Task: 创建的任务实例
        
        使用示例：
            task = protocol.create_task(
                "研究助手",
                "web_search",
                {"query": "LangGraph 教程"}
            )
        """
        # 创建任务
        task = task_manager.create_task(
            name=f"{target_agent}.{capability}",
            description=f"调用 {target_agent} 的 {capability} 能力",
            input_data={
                "target_agent": target_agent,
                "capability": capability,
                **input_data
            },
            metadata={"from": self.agent_name}
        )
        
        # 发送请求消息
        request = MessageFactory.create_request(
            from_agent=self.agent_name,
            to_agent=target_agent,
            content={
                "task_id": task.id,
                "capability": capability,
                "input": input_data
            },
            task_id=task.id
        )
        message_history.add_message(request)
        
        logger.info(f"创建任务: {task.name} (ID: {task.id})")
        return task
    
    async def execute_task(self, task_id: str) -> Task:
        """
        执行任务
        
        Args:
            task_id: 任务 ID
        
        Returns:
            Task: 执行后的任务实例
        
        使用示例：
            task = await protocol.execute_task("task-123")
            print(task.output_data)
        """
        task = task_manager.get_task(task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")
        
        target_agent = task.input_data.get("target_agent", "")
        capability = task.input_data.get("capability", "")
        
        # 更新状态为执行中
        task_manager.update_task_status(task_id, TaskStatus.RUNNING)
        
        # 发送状态通知
        notification = MessageFactory.create_notification(
            from_agent=self.agent_name,
            to_agent=target_agent,
            content={"task_id": task_id, "status": "running"}
        )
        message_history.add_message(notification)
        
        try:
            # 查找 Agent 处理器
            handler = self._agent_handlers.get(target_agent)
            if not handler:
                raise ValueError(f"未知的 Agent: {target_agent}")
            
            # 执行任务
            result = await handler(capability, task.input_data)
            
            # 更新状态为完成
            task_manager.update_task_status(
                task_id,
                TaskStatus.COMPLETED,
                progress=100,
                output_data=result
            )
            
            # 发送响应消息
            response = MessageFactory.create_response(
                from_agent=target_agent,
                to_agent=self.agent_name,
                content={"task_id": task_id, "result": result},
                task_id=task_id
            )
            message_history.add_message(response)
            
            logger.info(f"任务完成: {task.name}")
            return task_manager.get_task(task_id)
        
        except Exception as e:
            # 更新状态为失败
            task_manager.update_task_status(
                task_id,
                TaskStatus.FAILED,
                error=str(e)
            )
            
            # 发送错误消息
            error_msg = MessageFactory.create_error(
                from_agent=target_agent,
                to_agent=self.agent_name,
                error_message=str(e),
                task_id=task_id
            )
            message_history.add_message(error_msg)
            
            logger.error(f"任务失败: {task.name} - {e}")
            return task_manager.get_task(task_id)
    
    async def execute_multiple_tasks(self, task_ids: List[str]) -> List[Task]:
        """
        并行执行多个任务
        
        Args:
            task_ids: 任务 ID 列表
        
        Returns:
            List[Task]: 执行后的任务列表
        
        使用示例：
            tasks = await protocol.execute_multiple_tasks(["task-1", "task-2"])
        """
        logger.info(f"并行执行 {len(task_ids)} 个任务")
        results = await asyncio.gather(
            *[self.execute_task(tid) for tid in task_ids],
            return_exceptions=True
        )
        
        # 过滤异常结果
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"任务 {task_ids[i]} 执行异常: {result}")
            else:
                final_results.append(result)
        
        return final_results
    
    # ============================================================
    # Agent 处理器
    # ============================================================
    async def _handle_research_agent(self, capability: str, input_data: Dict) -> Dict:
        """
        研究助手 Agent 处理器
        
        处理研究助手的能力调用。
        """
        logger.info(f"研究助手处理: {capability}")
        
        if capability == "web_search":
            query = input_data.get("query", "")
            result = web_search.invoke({"query": query})
            return {"results": result}
        
        elif capability == "knowledge_search":
            query = input_data.get("query", "")
            result = search_knowledge.invoke({"query": query})
            return {"results": result}
        
        elif capability == "analyze":
            data = input_data.get("data", "")
            llm = get_llm()
            response = llm.invoke([
                ("system", "你是一个研究分析师。请分析以下数据并提取关键信息。"),
                ("human", data)
            ])
            return {"analysis": response.content}
        
        else:
            raise ValueError(f"未知能力: {capability}")
    
    async def _handle_coder_agent(self, capability: str, input_data: Dict) -> Dict:
        """
        编码助手 Agent 处理器
        
        处理编码助手的能力调用。
        """
        logger.info(f"编码助手处理: {capability}")
        
        if capability == "code_generation":
            description = input_data.get("description", "")
            language = input_data.get("language", "python")
            llm = get_llm()
            response = llm.invoke([
                ("system", f"你是一个 {language} 编程专家。根据需求生成代码。"),
                ("human", description)
            ])
            return {"code": response.content}
        
        elif capability == "code_review":
            code = input_data.get("code", "")
            llm = get_llm()
            response = llm.invoke([
                ("system", "你是一个代码审查专家。请审查以下代码并给出建议。"),
                ("human", code)
            ])
            return {"review": response.content}
        
        elif capability == "calculate":
            expression = input_data.get("expression", "")
            result = calculate.invoke({"expression": expression})
            return {"result": result}
        
        else:
            raise ValueError(f"未知能力: {capability}")
    
    async def _handle_summarizer_agent(self, capability: str, input_data: Dict) -> Dict:
        """
        总结助手 Agent 处理器
        
        处理总结助手的能力调用。
        """
        logger.info(f"总结助手处理: {capability}")
        
        if capability == "summarize":
            document = input_data.get("document", "")
            max_length = input_data.get("max_length", 500)
            llm = get_llm()
            response = llm.invoke([
                ("system", f"你是一个文档总结专家。请将文档总结为 {max_length} 字以内。"),
                ("human", document)
            ])
            return {"summary": response.content}
        
        elif capability == "extract_key_points":
            document = input_data.get("document", "")
            llm = get_llm()
            response = llm.invoke([
                ("system", "你是一个要点提取专家。请提取文档的关键要点。"),
                ("human", document)
            ])
            return {"key_points": response.content}
        
        else:
            raise ValueError(f"未知能力: {capability}")
    
    # ============================================================
    # 查询功能
    # ============================================================
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """
        查询任务状态
        
        Args:
            task_id: 任务 ID
        
        Returns:
            Dict: 任务状态信息
        """
        task = task_manager.get_task(task_id)
        if not task:
            return None
        return task.to_dict()
    
    def get_message_history(
        self,
        from_agent: str = None,
        to_agent: str = None,
        task_id: str = None
    ) -> List[Dict]:
        """
        获取消息历史
        
        Args:
            from_agent: 按发送者过滤
            to_agent: 按接收者过滤
            task_id: 按任务 ID 过滤
        
        Returns:
            List[Dict]: 消息列表
        """
        messages = message_history.get_messages(
            from_agent=from_agent,
            to_agent=to_agent,
            task_id=task_id
        )
        return [m.to_dict() for m in messages]


# 全局 A2A 协议实例
a2a_protocol = A2AProtocol()
