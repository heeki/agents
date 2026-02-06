"""A2A JSON-RPC Server for Life Sync Agent.

Implements the Google A2A protocol with streaming support.
All A2A methods are handled at POST / (root endpoint).
"""

import asyncio
import json
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sse_starlette.sse import EventSourceResponse

from .types import (
    AgentCard,
    AgentCapabilities,
    AgentSkill,
    Task,
    TaskStatus,
    Message,
    MessagePart,
    JsonRpcRequest,
    JsonRpcResponse,
    ErrorCode,
)
from agent import validate_workout, stream_validation, WorkoutPlan


# In-memory task store
tasks: dict[str, Task] = {}

# Agent configuration
AGENT_CARD = AgentCard(
    name="life-sync",
    description="Pragmatic logistics and lifestyle coordinator. Validates workout plans against real-world constraints: time, equipment, and fatigue.",
    url="http://localhost:8083",
    version="1.0.0",
    capabilities=AgentCapabilities(streaming=True, push_notifications=False),
    skills=[
        AgentSkill(
            id="validate-workout",
            name="Validate Workout Plan",
            description="Checks if a workout plan is feasible given the user's schedule and available equipment",
        ),
        AgentSkill(
            id="check-availability",
            name="Check Availability",
            description="Checks the user's calendar for free time slots",
        ),
        AgentSkill(
            id="check-equipment",
            name="Check Equipment",
            description="Checks what equipment is available at a specified location",
        ),
    ],
)


def create_a2a_app() -> FastAPI:
    """Create the FastAPI application with A2A endpoints."""
    app = FastAPI(title="Life Sync Agent - A2A Server")

    @app.get("/")
    async def root():
        """Root GET for basic health check."""
        return {"status": "healthy", "agent": "life-sync"}

    @app.post("/")
    async def root_post(request: Request):
        """Handle all A2A JSON-RPC requests at root endpoint.

        Dispatches to the appropriate handler based on the JSON-RPC method.
        For tasks/sendSubscribe, returns an SSE streaming response.
        """
        try:
            body = await request.json()
            rpc_request = JsonRpcRequest.from_dict(body)

            # Handle streaming requests
            if rpc_request.method == "tasks/sendSubscribe":
                return EventSourceResponse(
                    stream_task(rpc_request),
                    media_type="text/event-stream",
                )

            # Handle non-streaming requests
            response = await handle_rpc_request(rpc_request)
            return JSONResponse(content=response.to_dict())
        except Exception as e:
            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "id": body.get("id", "unknown") if 'body' in locals() else "unknown",
                    "error": {
                        "code": ErrorCode.INTERNAL_ERROR,
                        "message": str(e),
                    },
                },
                status_code=500,
            )

    @app.get("/.well-known/agent.json")
    async def get_agent_card():
        """Return the Agent Card for A2A discovery."""
        return AGENT_CARD.to_dict()

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy"}

    @app.get("/ping")
    async def ping():
        """Ping endpoint for AgentCore health checks."""
        return {"status": "ok"}

    return app


async def handle_rpc_request(request: JsonRpcRequest) -> JsonRpcResponse:
    """Handle a JSON-RPC request and return a response."""
    method_handlers = {
        "tasks/send": handle_task_send,
        "tasks/get": handle_task_get,
        "tasks/cancel": handle_task_cancel,
    }

    handler = method_handlers.get(request.method)
    if not handler:
        return JsonRpcResponse(
            jsonrpc="2.0",
            id=request.id,
            error={
                "code": ErrorCode.METHOD_NOT_FOUND,
                "message": f"Method not found: {request.method}",
            },
        )

    return await handler(request)


async def handle_task_send(request: JsonRpcRequest) -> JsonRpcResponse:
    """Handle tasks/send - validate a workout plan."""
    params = request.params
    task_data = params.get("task", {})

    task = Task.from_dict(task_data)
    task.status = TaskStatus.WORKING
    tasks[task.id] = task

    # Extract workout plan or request from message
    message_text = task.message.get_text()
    workout_plan = None
    location = None
    date = None

    # Check for structured data
    for part in task.message.parts:
        if part.data:
            if "workout" in part.data:
                workout_plan = WorkoutPlan.from_dict(part.data["workout"])
            if "location" in part.data:
                location = part.data["location"]
            if "date" in part.data:
                date = part.data["date"]

    try:
        # Validate the workout
        analysis = await validate_workout(
            workout_plan=workout_plan,
            raw_request=message_text,
            date=date,
            location=location,
        )

        # Build result message
        result_parts = [
            MessagePart(type="text", text=analysis.recommendation),
            MessagePart(type="data", data=analysis.to_dict()),
        ]
        result_message = Message(role="assistant", parts=result_parts)

        # Update task
        task.status = TaskStatus.COMPLETED
        task.result = result_message
        tasks[task.id] = task

        return JsonRpcResponse(
            jsonrpc="2.0",
            id=request.id,
            result={
                "taskId": task.id,
                "status": task.status.value,
                "result": result_message.to_dict(),
            },
        )

    except Exception as e:
        task.status = TaskStatus.FAILED
        tasks[task.id] = task

        return JsonRpcResponse(
            jsonrpc="2.0",
            id=request.id,
            error={
                "code": ErrorCode.INTERNAL_ERROR,
                "message": str(e),
            },
        )


async def handle_task_get(request: JsonRpcRequest) -> JsonRpcResponse:
    """Handle tasks/get - retrieve task status."""
    task_id = request.params.get("taskId")
    task = tasks.get(task_id)

    if not task:
        return JsonRpcResponse(
            jsonrpc="2.0",
            id=request.id,
            error={
                "code": ErrorCode.TASK_NOT_FOUND,
                "message": f"Task not found: {task_id}",
            },
        )

    return JsonRpcResponse(
        jsonrpc="2.0",
        id=request.id,
        result={
            "taskId": task.id,
            "status": task.status.value,
            "result": task.result.to_dict() if task.result else None,
        },
    )


async def handle_task_cancel(request: JsonRpcRequest) -> JsonRpcResponse:
    """Handle tasks/cancel - cancel a running task."""
    task_id = request.params.get("taskId")
    task = tasks.get(task_id)

    if not task:
        return JsonRpcResponse(
            jsonrpc="2.0",
            id=request.id,
            error={
                "code": ErrorCode.TASK_NOT_FOUND,
                "message": f"Task not found: {task_id}",
            },
        )

    task.status = TaskStatus.CANCELED
    tasks[task_id] = task

    return JsonRpcResponse(
        jsonrpc="2.0",
        id=request.id,
        result={
            "taskId": task.id,
            "status": TaskStatus.CANCELED.value,
        },
    )


async def stream_task(request: JsonRpcRequest):
    """Stream task execution via SSE."""
    params = request.params
    task_data = params.get("task", {})
    task = Task.from_dict(task_data)

    # Send initial status
    yield {
        "event": "task-status",
        "data": json.dumps({
            "taskId": task.id,
            "status": TaskStatus.WORKING.value,
            "message": "Checking constraints...",
        }),
    }

    message_text = task.message.get_text()
    workout_plan = None

    for part in task.message.parts:
        if part.data and "workout" in part.data:
            workout_plan = WorkoutPlan.from_dict(part.data["workout"])

    # Send progress update
    yield {
        "event": "task-status",
        "data": json.dumps({
            "taskId": task.id,
            "status": TaskStatus.WORKING.value,
            "message": "Checking calendar and equipment...",
        }),
    }

    try:
        full_content = ""
        async for chunk in stream_validation(workout_plan, message_text):
            full_content += chunk
            yield {
                "event": "task-chunk",
                "data": json.dumps({
                    "taskId": task.id,
                    "chunk": chunk,
                }),
            }

        # Send final result
        yield {
            "event": "task-result",
            "data": json.dumps({
                "taskId": task.id,
                "status": TaskStatus.COMPLETED.value,
                "result": {
                    "role": "assistant",
                    "parts": [{"type": "text", "text": full_content}],
                },
            }),
        }

    except Exception as e:
        yield {
            "event": "task-error",
            "data": json.dumps({
                "taskId": task.id,
                "status": TaskStatus.FAILED.value,
                "error": str(e),
            }),
        }
