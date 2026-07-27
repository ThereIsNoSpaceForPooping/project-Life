# -*- coding: utf-8 -*-
"""
MCP 工具定义

MCP 工具是 Agent 可以通过 MCP 协议调用的外部工具。
与 LangChain 工具不同，MCP 工具运行在独立的进程中。

学习要点：
1. MCP 工具通过 JSON-RPC 协议通信
2. 工具定义包含名称、描述、参数 schema
3. 工具调用是异步的
4. 工具可以运行在本地或远程

工具类型示例：
- 文件系统工具：读写文件、列出目录
- 数据库工具：查询数据库
- API 工具：调用外部 API
- 计算工具：执行代码、数学计算
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.core.logging import get_logger

logger = get_logger(__name__)


# ============================================================
# MCP 工具定义模型
# ============================================================
class MCPToolDefinition(BaseModel):
    """
    MCP 工具定义
    
    描述一个 MCP 工具的元数据，包括名称、描述、参数 schema。
    这个定义会发送给 LLM，让 LLM 知道有哪些工具可用。
    
    属性：
        name: 工具名称（唯一标识）
        description: 工具描述（LLM 会读取）
        parameters: 参数 JSON Schema
        required: 必需参数列表
    """
    name: str = Field(..., description="工具名称")
    description: str = Field(..., description="工具描述")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="参数 JSON Schema")
    required: List[str] = Field(default_factory=list, description="必需参数列表")


# ============================================================
# 预定义的 MCP 工具
# ============================================================

# 文件系统工具
FILESYSTEM_TOOLS = [
    MCPToolDefinition(
        name="read_file",
        description="读取文件内容",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径"
                },
                "encoding": {
                    "type": "string",
                    "description": "文件编码",
                    "default": "utf-8"
                }
            },
            "required": ["path"]
        },
        required=["path"]
    ),
    MCPToolDefinition(
        name="write_file",
        description="写入文件内容",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径"
                },
                "content": {
                    "type": "string",
                    "description": "文件内容"
                },
                "encoding": {
                    "type": "string",
                    "description": "文件编码",
                    "default": "utf-8"
                }
            },
            "required": ["path", "content"]
        },
        required=["path", "content"]
    ),
    MCPToolDefinition(
        name="list_directory",
        description="列出目录内容",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "目录路径"
                }
            },
            "required": ["path"]
        },
        required=["path"]
    ),
]

# 数据库工具
DATABASE_TOOLS = [
    MCPToolDefinition(
        name="query_database",
        description="执行 SQL 查询",
        parameters={
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "SQL 查询语句"
                },
                "params": {
                    "type": "array",
                    "description": "查询参数",
                    "items": {"type": "string"}
                }
            },
            "required": ["sql"]
        },
        required=["sql"]
    ),
    MCPToolDefinition(
        name="list_tables",
        description="列出数据库表",
        parameters={
            "type": "object",
            "properties": {}
        },
        required=[]
    ),
]

# 计算工具
COMPUTATION_TOOLS = [
    MCPToolDefinition(
        name="execute_code",
        description="执行 Python 代码",
        parameters={
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python 代码"
                }
            },
            "required": ["code"]
        },
        required=["code"]
    ),
    MCPToolDefinition(
        name="math_calculate",
        description="数学计算",
        parameters={
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "数学表达式"
                }
            },
            "required": ["expression"]
        },
        required=["expression"]
    ),
]

# API 工具
API_TOOLS = [
    MCPToolDefinition(
        name="http_request",
        description="发送 HTTP 请求",
        parameters={
            "type": "object",
            "properties": {
                "method": {
                    "type": "string",
                    "description": "HTTP 方法",
                    "enum": ["GET", "POST", "PUT", "DELETE"]
                },
                "url": {
                    "type": "string",
                    "description": "请求 URL"
                },
                "headers": {
                    "type": "object",
                    "description": "请求头"
                },
                "body": {
                    "type": "object",
                    "description": "请求体"
                }
            },
            "required": ["method", "url"]
        },
        required=["method", "url"]
    ),
]


# ============================================================
# 工具注册表
# ============================================================
class MCPToolRegistry:
    """
    MCP 工具注册表
    
    管理所有可用的 MCP 工具。
    支持按类别获取工具。
    """
    
    def __init__(self):
        """初始化工具注册表"""
        self._tools: Dict[str, MCPToolDefinition] = {}
        self._categories: Dict[str, List[str]] = {
            "filesystem": [],
            "database": [],
            "computation": [],
            "api": [],
        }
        
        # 注册默认工具
        self._register_default_tools()
    
    def _register_default_tools(self):
        """注册默认工具"""
        # 文件系统工具
        for tool in FILESYSTEM_TOOLS:
            self.register(tool, "filesystem")
        
        # 数据库工具
        for tool in DATABASE_TOOLS:
            self.register(tool, "database")
        
        # 计算工具
        for tool in COMPUTATION_TOOLS:
            self.register(tool, "computation")
        
        # API 工具
        for tool in API_TOOLS:
            self.register(tool, "api")
    
    def register(self, tool: MCPToolDefinition, category: str = "general"):
        """
        注册工具
        
        Args:
            tool: 工具定义
            category: 工具类别
        """
        self._tools[tool.name] = tool
        
        if category not in self._categories:
            self._categories[category] = []
        
        if tool.name not in self._categories[category]:
            self._categories[category].append(tool.name)
        
        logger.info(f"注册 MCP 工具: {tool.name} (类别: {category})")
    
    def get_tool(self, name: str) -> Optional[MCPToolDefinition]:
        """
        获取工具定义
        
        Args:
            name: 工具名称
        
        Returns:
            MCPToolDefinition: 工具定义，如果不存在则返回 None
        """
        return self._tools.get(name)
    
    def get_tools_by_category(self, category: str) -> List[MCPToolDefinition]:
        """
        按类别获取工具
        
        Args:
            category: 类别名称
        
        Returns:
            List[MCPToolDefinition]: 工具列表
        """
        tool_names = self._categories.get(category, [])
        return [self._tools[name] for name in tool_names if name in self._tools]
    
    def get_all_tools(self) -> List[MCPToolDefinition]:
        """
        获取所有工具
        
        Returns:
            List[MCPToolDefinition]: 所有工具列表
        """
        return list(self._tools.values())
    
    def to_openai_format(self) -> List[Dict[str, Any]]:
        """
        转换为 OpenAI 函数调用格式
        
        Returns:
            List[Dict]: OpenAI 格式的工具定义
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                }
            }
            for tool in self._tools.values()
        ]


# 全局工具注册表
mcp_tool_registry = MCPToolRegistry()
