# -*- coding: utf-8 -*-
"""
A2A 协议层 - 类型定义

按照 Google A2A 规范 v0.2 定义核心数据结构：
    - Task / TaskState / TaskStatus
    - Message / Part / TextPart / DataPart / FilePart
    - AgentCard / AgentSkill / AgentCapabilities
    - JSONRPCRequest / JSONRPCResponse / JSONRPCError
    - Artifact

所有类都提供：
    - to_dict()  - 序列化为符合规范的字典
    - from_dict() - 反序列化（仅输入类）
    - 严格类型注解
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger: logging.Logger = logging.getLogger("a2a.types")


# ============================================================
# 任务状态机
# ============================================================
class TaskState(str, Enum):
    """
    A2A 任务状态枚举

    状态转换图：
        submitted → working → completed
              │         │  ↘ failed
              │         └────→ input-required → working ...
              │         └────→ canceled
              └─────────────────→ canceled
              └─────────────────→ rejected
    """
    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input-required"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
    REJECTED = "rejected"

    def is_terminal(self) -> bool:
        """
        是否为终态

        终态包括：completed / failed / canceled / rejected
        """
        return self in (
            TaskState.COMPLETED,
            TaskState.FAILED,
            TaskState.CANCELED,
            TaskState.REJECTED,
        )


# ============================================================
# 多模态消息 Part
# ============================================================
@dataclass
class TextPart:
    """
    文本 Part

    A2A 中最常用的 Part 类型。
    """
    text: str
    type: str = "text"

    def to_dict(self) -> Dict[str, Any]:
        """序列化为符合 A2A 规范的字典"""
        return {"type": self.type, "text": self.text}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TextPart":
        """反序列化"""
        return cls(text=data.get("text", ""))


@dataclass
class DataPart:
    """
    结构化数据 Part

    用于传递 JSON 数据（如工具参数、结构化输出）。
    """
    data: Any
    type: str = "data"

    def to_dict(self) -> Dict[str, Any]:
        """序列化"""
        return {"type": self.type, "data": self.data}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DataPart":
        """反序列化"""
        return cls(data=data.get("data"))


@dataclass
class FilePart:
    """
    文件 Part

    支持两种传递方式：
        - 引用：{"file_uri": "https://..."}
        - 内联：{"file_bytes": "base64..."}
    """
    file_uri: Optional[str] = None
    file_bytes: Optional[str] = None  # base64
    mime_type: Optional[str] = None
    name: Optional[str] = None
    type: str = "file"

    def to_dict(self) -> Dict[str, Any]:
        """序列化"""
        result: Dict[str, Any] = {"type": self.type}
        if self.file_uri:
            result["file"] = {"uri": self.file_uri, "mimeType": self.mime_type or "application/octet-stream"}
        elif self.file_bytes:
            result["file"] = {
                "bytes": self.file_bytes,
                "mimeType": self.mime_type or "application/octet-stream",
            }
        if self.name:
            result["name"] = self.name
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FilePart":
        """反序列化"""
        file_data: Dict[str, Any] = data.get("file", {})
        return cls(
            file_uri=file_data.get("uri"),
            file_bytes=file_data.get("bytes"),
            mime_type=file_data.get("mimeType"),
            name=data.get("name"),
        )


def parse_parts(raw_parts: List[Dict[str, Any]]) -> List[Any]:
    """
    解析 Part 列表

    Args:
        raw_parts: 原始 Part 字典列表

    Returns:
        强类型 Part 对象列表
    """
    result: List[Any] = []
    for raw in raw_parts:
        part_type: str = raw.get("type", "text")
        if part_type == "text":
            result.append(TextPart.from_dict(raw))
        elif part_type == "data":
            result.append(DataPart.from_dict(raw))
        elif part_type == "file":
            result.append(FilePart.from_dict(raw))
        else:
            logger.warning("未知 Part 类型: %s", part_type)
            result.append(raw)
    return result


# ============================================================
# Message
# ============================================================
@dataclass
class Message:
    """
    A2A 消息

    角色：user / agent
    Parts：可包含多模态内容
    """
    role: str  # "user" | "agent"
    parts: List[Dict[str, Any]]
    message_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        """自动生成 messageId"""
        if not self.message_id:
            self.message_id = f"msg_{uuid.uuid4().hex[:12]}"

    def text_content(self) -> str:
        """提取纯文本内容"""
        texts: List[str] = []
        for part in self.parts:
            if part.get("type") == "text":
                texts.append(part.get("text", ""))
        return "\n".join(texts).strip()

    def to_dict(self) -> Dict[str, Any]:
        """序列化"""
        result: Dict[str, Any] = {
            "role": self.role,
            "parts": self.parts,
        }
        if self.message_id:
            result["messageId"] = self.message_id
        if self.metadata:
            result["metadata"] = self.metadata
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """反序列化"""
        return cls(
            role=data.get("role", "user"),
            parts=data.get("parts", []),
            message_id=data.get("messageId"),
            metadata=data.get("metadata"),
        )


# ============================================================
# Artifact（任务产物）
# ============================================================
@dataclass
class Artifact:
    """
    任务产物

    Agent 完成任务后产生的输出（最终结果、中间产物等）。
    """
    name: str
    parts: List[Dict[str, Any]]
    artifact_id: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        """自动生成 artifactId"""
        if not self.artifact_id:
            self.artifact_id = f"art_{uuid.uuid4().hex[:12]}"

    def to_dict(self) -> Dict[str, Any]:
        """序列化"""
        result: Dict[str, Any] = {
            "artifactId": self.artifact_id,
            "name": self.name,
            "parts": self.parts,
        }
        if self.description:
            result["description"] = self.description
        if self.metadata:
            result["metadata"] = self.metadata
        return result


# ============================================================
# TaskStatus
# ============================================================
@dataclass
class TaskStatus:
    """
    任务状态
    """
    state: TaskState
    message: Optional[Message] = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        """序列化"""
        result: Dict[str, Any] = {
            "state": self.state.value,
            "timestamp": self.timestamp,
        }
        if self.message:
            result["message"] = self.message.to_dict()
        return result


# ============================================================
# Task
# ============================================================
@dataclass
class Task:
    """
    A2A 任务

    完整生命周期：创建 → 执行 → 终止（含取消、失败）。
    """
    id: str
    agent_name: str
    status: TaskStatus
    messages: List[Message] = field(default_factory=list)
    artifacts: List[Artifact] = field(default_factory=list)
    history: List[TaskStatus] = field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None
    input_text: str = ""
    input_parts: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None

    def __post_init__(self) -> None:
        """初始化时记录历史"""
        self.history.append(self.status)

    @property
    def state(self) -> TaskState:
        """当前状态"""
        return self.status.state

    def is_terminal(self) -> bool:
        """是否已终止"""
        return self.status.state.is_terminal()

    def set_state(
        self,
        new_state: TaskState,
        message: Optional[Message] = None,
        error: Optional[str] = None,
    ) -> None:
        """
        状态转换（带历史记录）

        Args:
            new_state: 目标状态
            message: 可选状态消息
            error: 错误信息
        """
        self.status = TaskStatus(state=new_state, message=message)
        self.history.append(self.status)
        if error:
            self.error = error

    def add_message(self, message: Message) -> None:
        """追加消息"""
        self.messages.append(message)

    def add_artifact(self, artifact: Artifact) -> None:
        """追加产物"""
        self.artifacts.append(artifact)

    def to_dict(self) -> Dict[str, Any]:
        """序列化为 A2A 规范格式"""
        result: Dict[str, Any] = {
            "id": self.id,
            "agentName": self.agent_name,
            "status": self.status.to_dict(),
            "messages": [m.to_dict() for m in self.messages],
            "artifacts": [a.to_dict() for a in self.artifacts],
        }
        if self.metadata:
            result["metadata"] = self.metadata
        if self.session_id:
            result["sessionId"] = self.session_id
        if self.error:
            result["error"] = self.error
        return result


# ============================================================
# AgentCard
# ============================================================
@dataclass
class AgentSkill:
    """
    Agent 技能声明
    """
    id: str
    name: str
    description: str
    tags: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    input_modes: List[str] = field(default_factory=lambda: ["text"])
    output_modes: List[str] = field(default_factory=lambda: ["text"])

    def to_dict(self) -> Dict[str, Any]:
        """序列化"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "tags": self.tags,
            "examples": self.examples,
            "inputModes": self.input_modes,
            "outputModes": self.output_modes,
        }


@dataclass
class AgentCapabilities:
    """
    Agent 能力声明
    """
    streaming: bool = True
    push_notifications: bool = False
    state_transition_history: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """序列化"""
        return {
            "streaming": self.streaming,
            "pushNotifications": self.push_notifications,
            "stateTransitionHistory": self.state_transition_history,
        }


@dataclass
class AgentCard:
    """
    A2A Agent Card

    服务发现的核心：客户端通过 .well-known/agent.json 获取。
    """
    name: str
    description: str
    url: str
    version: str
    protocol_version: str
    capabilities: AgentCapabilities
    skills: List[AgentSkill]
    default_input_modes: List[str] = field(default_factory=lambda: ["text"])
    default_output_modes: List[str] = field(default_factory=lambda: ["text"])
    provider: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """序列化"""
        result: Dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "url": self.url,
            "version": self.version,
            "protocolVersion": self.protocol_version,
            "capabilities": self.capabilities.to_dict(),
            "skills": [s.to_dict() for s in self.skills],
            "defaultInputModes": self.default_input_modes,
            "defaultOutputModes": self.default_output_modes,
        }
        if self.provider:
            result["provider"] = self.provider
        return result


# ============================================================
# JSON-RPC 类型
# ============================================================
@dataclass
class JSONRPCRequest:
    """
    JSON-RPC 2.0 请求
    """
    method: str
    params: Dict[str, Any] = field(default_factory=dict)
    id: Any = None
    jsonrpc: str = "2.0"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JSONRPCRequest":
        """反序列化"""
        return cls(
            method=data.get("method", ""),
            params=data.get("params", {}),
            id=data.get("id"),
            jsonrpc=data.get("jsonrpc", "2.0"),
        )


@dataclass
class JSONRPCResponse:
    """
    JSON-RPC 2.0 响应
    """
    id: Any
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    jsonrpc: str = "2.0"

    def to_dict(self) -> Dict[str, Any]:
        """序列化"""
        response: Dict[str, Any] = {"jsonrpc": self.jsonrpc, "id": self.id}
        if self.error is not None:
            response["error"] = self.error
        else:
            response["result"] = self.result
        return response


# ============================================================
# 流式响应
# ============================================================
@dataclass
class StreamResponse:
    """
    流式响应事件

    用于 SSE 流式输出。
    """
    type: str  # "status" | "message" | "artifact" | "end"
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """序列化"""
        result: Dict[str, Any] = {"type": self.type}
        result.update(self.data)
        return result
