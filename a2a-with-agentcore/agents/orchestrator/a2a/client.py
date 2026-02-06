"""A2A Client for calling sub-agents.

Implements the A2A protocol client with retry logic and streaming support.
Supports both HTTP (local) and boto3 AgentCore (deployed) modes.
"""

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any, AsyncGenerator

import httpx

from .types import (
    Task,
    TaskStatus,
    Message,
    MessagePart,
    JsonRpcRequest,
    JsonRpcResponse,
    ErrorCode,
)


def _is_arn(value: str) -> bool:
    """Check if a string is an AWS ARN."""
    return value.startswith("arn:aws:")


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 10.0
    exponential_base: float = 2.0
    retryable_errors: tuple[str, ...] = (
        "ServiceUnavailable",
        "ThrottlingException",
        "Timeout",
        "Connection refused",
        "Connection reset",
    )


class A2AClient:
    """Client for communicating with A2A-compliant agents.

    Supports both HTTP (local) and boto3 AgentCore (deployed) modes.
    Mode is automatically detected based on whether agent_url is an ARN.
    """

    def __init__(
        self,
        agent_url: str,
        agent_name: str,
        timeout: float = 60.0,
        retry_config: RetryConfig | None = None,
    ):
        """Initialize the A2A client.

        Args:
            agent_url: Base URL or ARN of the target agent.
            agent_name: Name of the target agent (for logging).
            timeout: Request timeout in seconds.
            retry_config: Configuration for retry behavior.
        """
        self.agent_url = agent_url.rstrip("/")
        self.agent_name = agent_name
        self.timeout = timeout
        self.retry_config = retry_config or RetryConfig()
        self._client: httpx.AsyncClient | None = None
        self._use_agentcore = _is_arn(agent_url)
        self._boto_client = None

        if self._use_agentcore:
            # Lazy import boto3 only when needed
            import boto3
            region = os.getenv("AWS_REGION", "us-east-1")
            self._boto_client = boto3.client("bedrock-agentcore", region_name=region)

    async def __aenter__(self) -> "A2AClient":
        self._client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def get_agent_card(self) -> dict[str, Any]:
        """Fetch the agent's Agent Card for discovery."""
        response = await self.client.get(
            f"{self.agent_url}/.well-known/agent.json"
        )
        response.raise_for_status()
        return response.json()

    async def send_task(
        self,
        task_id: str,
        message: Message,
        retry: bool = True,
    ) -> dict[str, Any]:
        """Send a task to the agent.

        Args:
            task_id: Unique identifier for the task.
            message: The message to send.
            retry: Whether to retry on failure.

        Returns:
            Task result with status and response.

        Raises:
            A2AError: If the request fails after all retries.
        """
        request = JsonRpcRequest(
            jsonrpc="2.0",
            id=task_id,
            method="tasks/send",
            params={
                "task": {
                    "id": task_id,
                    "message": message.to_dict(),
                }
            },
        )

        return await self._send_with_retry(request, retry)

    async def send_task_subscribe(
        self,
        task_id: str,
        message: Message,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Send a task and subscribe to streaming updates.

        Args:
            task_id: Unique identifier for the task.
            message: The message to send.

        Yields:
            SSE events with task updates.
        """
        request_body = {
            "jsonrpc": "2.0",
            "id": task_id,
            "method": "tasks/sendSubscribe",
            "params": {
                "task": {
                    "id": task_id,
                    "message": message.to_dict(),
                }
            },
        }

        async with self.client.stream(
            "POST",
            f"{self.agent_url}/",
            json=request_body,
            headers={"Accept": "text/event-stream"},
        ) as response:
            response.raise_for_status()

            event_type = ""
            async for line in response.aiter_lines():
                if not line:
                    continue

                if line.startswith("event:"):
                    event_type = line[6:].strip()
                elif line.startswith("data:"):
                    data = json.loads(line[5:].strip())
                    yield {"event": event_type, "data": data}

    async def get_task(self, task_id: str) -> dict[str, Any]:
        """Get the status and result of a task.

        Args:
            task_id: The task ID to query.

        Returns:
            Task status and result.
        """
        request = JsonRpcRequest(
            jsonrpc="2.0",
            id=f"get-{task_id}",
            method="tasks/get",
            params={"taskId": task_id},
        )

        return await self._send_request(request)

    async def cancel_task(self, task_id: str) -> dict[str, Any]:
        """Cancel a running task.

        Args:
            task_id: The task ID to cancel.

        Returns:
            Cancellation confirmation.
        """
        request = JsonRpcRequest(
            jsonrpc="2.0",
            id=f"cancel-{task_id}",
            method="tasks/cancel",
            params={"taskId": task_id},
        )

        return await self._send_request(request)

    async def _send_request(
        self,
        request: JsonRpcRequest,
    ) -> dict[str, Any]:
        """Send a JSON-RPC request to the agent."""
        request_payload = {
            "jsonrpc": request.jsonrpc,
            "id": request.id,
            "method": request.method,
            "params": request.params,
        }

        if self._use_agentcore:
            # Use boto3 AgentCore client
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                self._invoke_agentcore,
                request_payload
            )
        else:
            # Use HTTP
            response = await self.client.post(
                f"{self.agent_url}/",
                json=request_payload,
            )
            response.raise_for_status()
            return response.json()

    def _invoke_agentcore(self, request_payload: dict[str, Any]) -> dict[str, Any]:
        """Invoke AgentCore runtime synchronously (runs in executor)."""
        response = self._boto_client.invoke_agent_runtime(
            agentRuntimeArn=self.agent_url,
            qualifier="DEFAULT",
            contentType="application/json",
            accept="application/json",
            payload=json.dumps(request_payload),
        )

        # Parse response body
        response_body = response.get("response")
        if hasattr(response_body, 'read'):
            raw = response_body.read().decode("utf-8")
        else:
            raw = ""
            for chunk in response_body:
                raw += chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk

        return json.loads(raw)

    async def _send_with_retry(
        self,
        request: JsonRpcRequest,
        retry: bool = True,
    ) -> dict[str, Any]:
        """Send a request with retry logic."""
        last_error: Exception | None = None
        attempts = self.retry_config.max_attempts if retry else 1

        for attempt in range(attempts):
            try:
                result = await self._send_request(request)

                # Check for JSON-RPC error
                if "error" in result:
                    error = result["error"]
                    error_msg = error.get("message", "Unknown error")

                    # Check if error is retryable
                    is_retryable = any(
                        re in error_msg
                        for re in self.retry_config.retryable_errors
                    )

                    if is_retryable and attempt < attempts - 1:
                        delay = min(
                            self.retry_config.base_delay_seconds
                            * (self.retry_config.exponential_base ** attempt),
                            self.retry_config.max_delay_seconds,
                        )
                        await asyncio.sleep(delay)
                        continue

                    raise A2AError(
                        agent=self.agent_name,
                        code=error.get("code", ErrorCode.INTERNAL_ERROR),
                        message=error_msg,
                        data=error.get("data"),
                    )

                return result

            except httpx.HTTPStatusError as e:
                last_error = e
                if attempt < attempts - 1:
                    delay = min(
                        self.retry_config.base_delay_seconds
                        * (self.retry_config.exponential_base ** attempt),
                        self.retry_config.max_delay_seconds,
                    )
                    await asyncio.sleep(delay)
                    continue

            except httpx.ConnectError as e:
                last_error = e
                if attempt < attempts - 1:
                    delay = min(
                        self.retry_config.base_delay_seconds
                        * (self.retry_config.exponential_base ** attempt),
                        self.retry_config.max_delay_seconds,
                    )
                    await asyncio.sleep(delay)
                    continue

        raise A2AError(
            agent=self.agent_name,
            code=ErrorCode.AGENT_UNAVAILABLE,
            message=f"Agent unavailable after {attempts} retries",
            data={"lastError": str(last_error)} if last_error else None,
        )


class A2AError(Exception):
    """Error from an A2A agent call."""

    def __init__(
        self,
        agent: str,
        code: int,
        message: str,
        data: dict[str, Any] | None = None,
    ):
        self.agent = agent
        self.code = code
        self.message = message
        self.data = data
        super().__init__(f"[{agent}] {message}")


# Pre-configured clients for sub-agents
def get_biomechanics_client() -> A2AClient:
    """Get A2A client for the Biomechanics Lab agent.

    Checks for ARN or URL from environment variables.
    - BIOMECHANICS_ARN: Use boto3 AgentCore (deployed mode)
    - BIOMECHANICS_URL: Use HTTP (local mode)
    """
    arn_or_url = os.environ.get("BIOMECHANICS_ARN") or os.environ.get("BIOMECHANICS_URL", "http://localhost:8082")
    return A2AClient(arn_or_url, "biomechanics-lab")


def get_life_sync_client() -> A2AClient:
    """Get A2A client for the Life Sync agent.

    Checks for ARN or URL from environment variables.
    - LIFESYNC_ARN: Use boto3 AgentCore (deployed mode)
    - LIFESYNC_URL: Use HTTP (local mode)
    """
    arn_or_url = os.environ.get("LIFESYNC_ARN") or os.environ.get("LIFESYNC_URL", "http://localhost:8083")
    return A2AClient(arn_or_url, "life-sync")
