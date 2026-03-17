"""A2A Protocol v1 Type Definitions.

Implements the Google A2A (Agent-to-Agent) protocol types per the v1 specification.
JSON-RPC methods: SendMessage, SendStreamingMessage, GetTask, CancelTask.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid


class TaskState(str, Enum):
    """Task execution state per A2A v1 spec."""
    SUBMITTED = "submitted"
    WORKING = "working"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
    INPUT_REQUIRED = "input-required"
    AUTH_REQUIRED = "auth-required"
    REJECTED = "rejected"


@dataclass
class Part:
    """A content part in a message or artifact.

    Uses flat structure with optional fields per v1 spec.
    """
    text: str | None = None
    data: Any | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if self.text is not None:
            result["text"] = self.text
        if self.data is not None:
            result["data"] = self.data
        if self.metadata is not None:
            result["metadata"] = self.metadata
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Part":
        return cls(
            text=data.get("text"),
            data=data.get("data"),
            metadata=data.get("metadata"),
        )


@dataclass
class Message:
    """A message in the A2A v1 protocol."""
    role: str  # "user" or "agent"
    parts: list[Part] = field(default_factory=list)
    messageId: str = field(default_factory=lambda: str(uuid.uuid4()))
    contextId: str | None = None
    taskId: str | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "role": self.role,
            "parts": [p.to_dict() for p in self.parts],
            "messageId": self.messageId,
        }
        if self.contextId is not None:
            result["contextId"] = self.contextId
        if self.taskId is not None:
            result["taskId"] = self.taskId
        if self.metadata is not None:
            result["metadata"] = self.metadata
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Message":
        return cls(
            role=data.get("role", "user"),
            parts=[Part.from_dict(p) for p in data.get("parts", [])],
            messageId=data.get("messageId", str(uuid.uuid4())),
            contextId=data.get("contextId"),
            taskId=data.get("taskId"),
            metadata=data.get("metadata"),
        )

    def get_text(self) -> str:
        """Extract all text parts concatenated."""
        return " ".join(p.text for p in self.parts if p.text)


@dataclass
class TaskStatus:
    """Task status with state, optional message, and timestamp."""
    state: TaskState
    message: Message | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "state": self.state.value,
            "timestamp": self.timestamp,
        }
        if self.message is not None:
            result["message"] = self.message.to_dict()
        return result


@dataclass
class Artifact:
    """An artifact produced by a task."""
    artifactId: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str | None = None
    description: str | None = None
    parts: list[Part] = field(default_factory=list)
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "artifactId": self.artifactId,
            "parts": [p.to_dict() for p in self.parts],
        }
        if self.name is not None:
            result["name"] = self.name
        if self.description is not None:
            result["description"] = self.description
        if self.metadata is not None:
            result["metadata"] = self.metadata
        return result


@dataclass
class Task:
    """A task in the A2A v1 protocol."""
    id: str
    status: TaskStatus
    contextId: str | None = None
    artifacts: list[Artifact] = field(default_factory=list)
    history: list[Message] = field(default_factory=list)
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "status": self.status.to_dict(),
        }
        if self.contextId is not None:
            result["contextId"] = self.contextId
        if self.artifacts:
            result["artifacts"] = [a.to_dict() for a in self.artifacts]
        if self.history:
            result["history"] = [m.to_dict() for m in self.history]
        if self.metadata is not None:
            result["metadata"] = self.metadata
        return result


@dataclass
class TaskStatusUpdateEvent:
    """Streaming event for task status changes."""
    taskId: str
    status: TaskStatus
    contextId: str | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "taskId": self.taskId,
            "status": self.status.to_dict(),
        }
        if self.contextId is not None:
            result["contextId"] = self.contextId
        if self.metadata is not None:
            result["metadata"] = self.metadata
        return result


@dataclass
class TaskArtifactUpdateEvent:
    """Streaming event for artifact updates."""
    taskId: str
    artifact: Artifact
    contextId: str | None = None
    append: bool = False
    lastChunk: bool = True
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "taskId": self.taskId,
            "artifact": self.artifact.to_dict(),
            "append": self.append,
            "lastChunk": self.lastChunk,
        }
        if self.contextId is not None:
            result["contextId"] = self.contextId
        if self.metadata is not None:
            result["metadata"] = self.metadata
        return result


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
            id=data.get("id", str(uuid.uuid4())),
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
    authentication: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        result = {
            "name": self.name,
            "description": self.description,
            "url": self.url,
            "version": self.version,
            "capabilities": self.capabilities.to_dict(),
            "skills": [s.to_dict() for s in self.skills],
        }
        if self.authentication is not None:
            result["authentication"] = self.authentication
        return result
