# -*- coding: utf-8 -*-
"""
A2A Agent Card 实现

Agent Card 是 A2A（Agent-to-Agent）协议的核心概念。
它描述了 Agent 的能力、接口和通信方式，类似于"名片"。

学习要点：
1. Agent Card 是 Agent 的"名片"，描述其能力
2. 其他 Agent 通过 Agent Card 发现和理解这个 Agent
3. Agent Card 包含：名称、描述、能力、端点等
4. 类似于 REST API 的 OpenAPI 规范

架构图：
    Agent A                          Agent B
       │                                │
       │── 获取 Agent Card ────────────▶│
       │◀── 返回 Agent Card ────────────│
       │                                │
       │   (Agent Card 包含：            │
       │    - 名称: "研究助手"           │
       │    - 能力: ["搜索", "分析"]     │
       │    - 端点: "/a2a/research")     │
       │                                │
       │── 发送任务 ───────────────────▶│
       │◀── 返回结果 ──────────────────│
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.core.logging import get_logger

logger = get_logger(__name__)


# ============================================================
# Agent 能力定义
# ============================================================
class AgentCapability(BaseModel):
    """
    Agent 能力定义
    
    描述 Agent 能做什么。
    
    属性：
        name: 能力名称
        description: 能力描述
        input_schema: 输入参数 schema
        output_schema: 输出结果 schema
    """
    name: str = Field(..., description="能力名称")
    description: str = Field(..., description="能力描述")
    input_schema: Dict[str, Any] = Field(default_factory=dict, description="输入参数 schema")
    output_schema: Dict[str, Any] = Field(default_factory=dict, description="输出结果 schema")


# ============================================================
# Agent Card 定义
# ============================================================
class AgentCard(BaseModel):
    """
    Agent Card - Agent 的"名片"
    
    描述 Agent 的完整信息，包括：
    - 基本信息（名称、描述、版本）
    - 能力列表
    - 通信端点
    - 认证方式
    
    属性：
        name: Agent 名称
        description: Agent 描述
        version: Agent 版本
        capabilities: 能力列表
        endpoint: 通信端点 URL
        auth_type: 认证类型（none / api_key / oauth）
        metadata: 额外元数据
    """
    name: str = Field(..., description="Agent 名称")
    description: str = Field(..., description="Agent 描述")
    version: str = Field(default="1.0.0", description="Agent 版本")
    capabilities: List[AgentCapability] = Field(default_factory=list, description="能力列表")
    endpoint: str = Field(..., description="通信端点 URL")
    auth_type: str = Field(default="none", description="认证类型")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="额外元数据")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式
        
        Returns:
            Dict: Agent Card 的字典表示
        """
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "capabilities": [
                {
                    "name": cap.name,
                    "description": cap.description,
                    "inputSchema": cap.input_schema,
                    "outputSchema": cap.output_schema,
                }
                for cap in self.capabilities
            ],
            "endpoint": self.endpoint,
            "authType": self.auth_type,
            "metadata": self.metadata,
        }


# ============================================================
# 预定义的 Agent Card
# ============================================================

# 研究助手 Agent Card
RESEARCH_AGENT_CARD = AgentCard(
    name="研究助手",
    description="专注于信息搜索和分析的 Agent",
    version="1.0.0",
    capabilities=[
        AgentCapability(
            name="web_search",
            description="网络搜索能力",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"}
                },
                "required": ["query"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "results": {"type": "array", "description": "搜索结果列表"}
                }
            }
        ),
        AgentCapability(
            name="knowledge_search",
            description="知识库搜索能力",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"}
                },
                "required": ["query"]
            }
        ),
        AgentCapability(
            name="analyze",
            description="信息分析能力",
            input_schema={
                "type": "object",
                "properties": {
                    "data": {"type": "string", "description": "待分析的数据"}
                },
                "required": ["data"]
            }
        ),
    ],
    endpoint="/a2a/research",
    auth_type="none",
    metadata={"specialty": "research", "language": ["zh", "en"]}
)

# 编码助手 Agent Card
CODER_AGENT_CARD = AgentCard(
    name="编码助手",
    description="专注于代码生成和数学计算的 Agent",
    version="1.0.0",
    capabilities=[
        AgentCapability(
            name="code_generation",
            description="代码生成能力",
            input_schema={
                "type": "object",
                "properties": {
                    "description": {"type": "string", "description": "代码需求描述"},
                    "language": {"type": "string", "description": "编程语言", "default": "python"}
                },
                "required": ["description"]
            }
        ),
        AgentCapability(
            name="code_review",
            description="代码审查能力",
            input_schema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "待审查的代码"}
                },
                "required": ["code"]
            }
        ),
        AgentCapability(
            name="calculate",
            description="数学计算能力",
            input_schema={
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "数学表达式"}
                },
                "required": ["expression"]
            }
        ),
    ],
    endpoint="/a2a/coder",
    auth_type="none",
    metadata={"specialty": "coding", "language": ["python", "javascript", "go"]}
)

# 总结助手 Agent Card
SUMMARIZER_AGENT_CARD = AgentCard(
    name="总结助手",
    description="专注于文档总结和整理的 Agent",
    version="1.0.0",
    capabilities=[
        AgentCapability(
            name="summarize",
            description="文档总结能力",
            input_schema={
                "type": "object",
                "properties": {
                    "document": {"type": "string", "description": "待总结的文档"},
                    "max_length": {"type": "integer", "description": "最大长度", "default": 500}
                },
                "required": ["document"]
            }
        ),
        AgentCapability(
            name="extract_key_points",
            description="提取要点能力",
            input_schema={
                "type": "object",
                "properties": {
                    "document": {"type": "string", "description": "待分析的文档"}
                },
                "required": ["document"]
            }
        ),
    ],
    endpoint="/a2a/summarizer",
    auth_type="none",
    metadata={"specialty": "summarization"}
)


# ============================================================
# Agent Card 注册表
# ============================================================
class AgentCardRegistry:
    """
    Agent Card 注册表
    
    管理所有可用的 Agent Card。
    支持注册、查询、发现 Agent。
    """
    
    def __init__(self):
        """初始化注册表"""
        self._agents: Dict[str, AgentCard] = {}
        self._register_default_agents()
    
    def _register_default_agents(self):
        """注册默认的 Agent"""
        self.register(RESEARCH_AGENT_CARD)
        self.register(CODER_AGENT_CARD)
        self.register(SUMMARIZER_AGENT_CARD)
    
    def register(self, card: AgentCard):
        """
        注册 Agent Card
        
        Args:
            card: Agent Card 实例
        """
        self._agents[card.name] = card
        logger.info(f"注册 Agent: {card.name}")
    
    def get(self, name: str) -> Optional[AgentCard]:
        """
        获取 Agent Card
        
        Args:
            name: Agent 名称
        
        Returns:
            AgentCard: Agent Card 实例
        """
        return self._agents.get(name)
    
    def list_agents(self) -> List[AgentCard]:
        """
        列出所有 Agent
        
        Returns:
            List[AgentCard]: 所有 Agent Card 列表
        """
        return list(self._agents.values())
    
    def discover(self, capability: str) -> List[AgentCard]:
        """
        根据能力发现 Agent
        
        Args:
            capability: 能力名称
        
        Returns:
            List[AgentCard]: 具有该能力的 Agent 列表
        """
        matching_agents = []
        
        for agent in self._agents.values():
            for cap in agent.capabilities:
                if capability.lower() in cap.name.lower() or capability.lower() in cap.description.lower():
                    matching_agents.append(agent)
                    break
        
        logger.info(f"发现 {len(matching_agents)} 个具有 '{capability}' 能力的 Agent")
        return matching_agents


# 全局注册表
agent_card_registry = AgentCardRegistry()
