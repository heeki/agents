"""A2A Protocol Type Definitions.

Implements the Google A2A (Agent-to-Agent) protocol types for
JSON-RPC based agent communication.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    WORKING = "working"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


@dataclass
class MessagePart:
    """A part of a message (text or data)."""
    type: str  # "text" or "data"
    text: str | None = None
    data: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"type": self.type}
        if self.text is not None:
            result["text"] = self.text
        if self.data is not None:
            result["data"] = self.data
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MessagePart":
        return cls(
            type=data["type"],
            text=data.get("text"),
            data=data.get("data"),
        )


@dataclass
class Message:
    """A message in the A2A protocol."""
    role: str  # "user" or "assistant"
    parts: list[MessagePart] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "parts": [p.to_dict() for p in self.parts],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Message":
        return cls(
            role=data["role"],
            parts=[MessagePart.from_dict(p) for p in data.get("parts", [])],
        )

    def get_text(self) -> str:
        """Extract all text parts concatenated."""
        return " ".join(p.text for p in self.parts if p.text)


@dataclass
class Task:
    """A task in the A2A protocol."""
    id: str
    message: Message
    status: TaskStatus = TaskStatus.PENDING
    result: Message | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "message": self.message.to_dict(),
            "status": self.status.value,
        }
        if self.result is not None:
            result["result"] = self.result.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Task":
        return cls(
            id=data["id"],
            message=Message.from_dict(data["message"]),
            status=TaskStatus(data.get("status", "pending")),
            result=Message.from_dict(data["result"]) if data.get("result") else None,
        )


@dataclass
class JsonRpcRequest:
    """JSON-RPC 2.0 request."""
    jsonrpc: str
    id: str
    method: str
    params: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JsonRpcRequest":
        return cls(
            jsonrpc=data.get("jsonrpc", "2.0"),
            id=data["id"],
            method=data["method"],
            params=data.get("params", {}),
        )


@dataclass
class JsonRpcResponse:
    """JSON-RPC 2.0 response."""
    jsonrpc: str
    id: str
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        response: dict[str, Any] = {
            "jsonrpc": self.jsonrpc,
            "id": self.id,
        }
        if self.result is not None:
            response["result"] = self.result
        if self.error is not None:
            response["error"] = self.error
        return response


@dataclass
class JsonRpcError:
    """JSON-RPC 2.0 error."""
    code: int
    message: str
    data: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
        }
        if self.data is not None:
            result["data"] = self.data
        return result


# Standard JSON-RPC error codes
class ErrorCode:
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    # Custom A2A error codes
    TASK_NOT_FOUND = -32000
    AGENT_UNAVAILABLE = -32001
    TASK_CANCELED = -32002


@dataclass
class AgentSkill:
    """A skill that an agent can perform."""
    id: str
    name: str
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
        }


@dataclass
class AgentCapabilities:
    """Capabilities of an agent."""
    streaming: bool = True
    push_notifications: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "streaming": self.streaming,
            "pushNotifications": self.push_notifications,
        }


@dataclass
class AgentCard:
    """Agent Card for A2A discovery."""
    name: str
    description: str
    url: str
    version: str = "1.0.0"
    capabilities: AgentCapabilities = field(default_factory=AgentCapabilities)
    skills: list[AgentSkill] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "url": self.url,
            "version": self.version,
            "capabilities": self.capabilities.to_dict(),
            "skills": [s.to_dict() for s in self.skills],
        }
