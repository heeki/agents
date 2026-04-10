"""A2A v1 JSON-RPC Server for Orchestrator Agent.

Implements the Google A2A v1 protocol with streaming support.
JSON-RPC methods: SendMessage, SendStreamingMessage, GetTask, CancelTask.
"""

import asyncio
import json
import os
import re
import traceback
import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from .auth import oauth2_middleware
from .types import (
    AgentCard,
    AgentCapabilities,
    AgentSkill,
    Artifact,
    ErrorCode,
    JsonRpcRequest,
    JsonRpcResponse,
    Message,
    Part,
    Task,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
)

# Import the Strands agent
from strands import Agent
from strands.models import BedrockModel
from tools import call_biomechanics_lab, call_life_sync_agent, request_workout_compromise


# In-memory task store
tasks: dict[str, Task] = {}

# Agent configuration
COGNITO_DOMAIN = os.environ.get("COGNITO_DOMAIN", "")

AGENT_CARD = AgentCard(
    name="orchestrator",
    description="Central coordinator for the fitness multi-agent system. Translates user goals into workout plans and resolves conflicts between ideal training and real-world constraints.",
    url=os.environ.get("ORCHESTRATOR_URL", "http://localhost:8081"),
    version="1.0.0",
    capabilities=AgentCapabilities(streaming=True, push_notifications=False),
    skills=[
        AgentSkill(
            id="create-workout",
            name="Create Workout Plan",
            description="Creates a personalized workout plan considering user goals and constraints",
        ),
        AgentSkill(
            id="adaptive-planning",
            name="Adaptive Planning",
            description="Adjusts workout plans when conflicts with schedule or equipment are detected",
        ),
    ],
    authentication={
        "schemes": ["OAuth2"],
        "credentials": {
            "oauth2": {
                "tokenUrl": f"{COGNITO_DOMAIN}/oauth2/token" if COGNITO_DOMAIN else "",
                "scopes": {
                    "a2a-fitness-api/invoke": "Invoke fitness agents",
                    "a2a-fitness-api/read": "Read agent cards and status",
                },
            }
        },
    } if COGNITO_DOMAIN else None,
)

SYSTEM_PROMPT = """You are the central coordinator for a fitness multi-agent system.

Objective: Translate high-level user goals into actionable workout plans and resolve
conflicts between "ideal training" and "life reality."

Your workflow:
1. When a user requests a workout, first call the Biomechanics Lab to get the
   physiologically optimal workout using call_biomechanics_lab.
   - IMPORTANT: Always provide equipment and muscle_groups as lists, use [] if none specified
   - Example: call_biomechanics_lab(goal="upper body strength", equipment=[], muscle_groups=[], duration_minutes=60)

2. Once you have the workout, call the Life Sync Agent using call_life_sync_agent
   to check calendar availability and equipment.
   - IMPORTANT: Always provide required_equipment as a list, use [] for bodyweight workouts
   - Example: call_life_sync_agent(workout_name="Upper Body", duration_minutes=60, required_equipment=[])

3. If the Life Sync agent reports conflicts (time or equipment issues):
   - Call request_workout_compromise to get a modified workout
   - IMPORTANT: Always provide available_equipment as a list, use [] for bodyweight only
   - The compromise will prioritize intensity over duration

4. Return the final, validated workout plan to the user in BOTH formats:
   a) A friendly text summary for human reading
   b) A structured JSON object for programmatic parsing

CRITICAL: Your response MUST include a JSON code block with this exact structure:
```json
{
  "workout": {
    "title": "Workout Name",
    "exercises": [
      {
        "number": 1,
        "name": "Exercise Name",
        "muscle_group": "Muscle Group",
        "equipment": "Equipment List",
        "sets": 3,
        "reps": "8-12",
        "duration": "30 minutes (or null if not applicable)",
        "rest": "60 seconds",
        "notes": "Any important notes"
      }
    ]
  },
  "schedule": {
    "available_times": ["06:00-07:00", "12:00-13:00"],
    "message": "Schedule availability message"
  }
}
```

Important:
- Always validate the workout before presenting it to the user
- If there are any conflicts, explain them clearly and present the compromise
- Be decisive and results-oriented in your responses
- Include BOTH the friendly text summary AND the JSON structure in every response

Tone: Professional, decisive, and results-oriented."""


def create_strands_agent() -> Agent:
    """Create the Strands agent with A2A tools."""
    model = BedrockModel(
        model_id=os.environ.get("MODEL_ID", "us.amazon.nova-lite-v1:0"),
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )

    agent = Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[
            call_biomechanics_lab,
            call_life_sync_agent,
            request_workout_compromise,
        ],
    )

    return agent


def extract_message_from_params(params: dict[str, Any]) -> Message:
    """Extract Message from SendMessage/SendStreamingMessage params."""
    msg_data = params.get("message", {})
    msg = Message.from_dict(msg_data)
    return msg


def run_agent_and_build_result(message_text: str, task_id: str, context_id: str | None) -> tuple[list[Part], list[Artifact]]:
    """Run the Strands agent synchronously and return parts and artifacts."""
    agent = create_strands_agent()
    result = agent(message_text)
    result_text = str(result)

    parts = [Part(kind="text", text=result_text)]
    artifacts = []

    # Extract structured JSON from the response
    json_match = re.search(r'```json\s*\n?(.*?)\n?```', result_text, re.DOTALL)
    if json_match:
        try:
            json_text = json_match.group(1).strip()
            structured_data = json.loads(json_text)
            artifacts.append(Artifact(
                name="workout-plan",
                description="Structured workout plan",
                parts=[Part(kind="data", data=structured_data)],
            ))
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")

    return parts, artifacts


def create_a2a_app() -> FastAPI:
    """Create the FastAPI application with A2A endpoints."""
    app = FastAPI(title="Orchestrator Agent - A2A Server")
    app.middleware("http")(oauth2_middleware)

    @app.get("/")
    async def root():
        """Root GET for basic health check."""
        return {"status": "healthy", "agent": "orchestrator"}

    @app.post("/")
    async def root_post(request: Request):
        """Handle all A2A JSON-RPC requests at root endpoint.

        Dispatches based on the JSON-RPC method field.
        v1 methods: SendMessage, SendStreamingMessage, GetTask, CancelTask.
        """
        try:
            body = await request.json()
            rpc_request = JsonRpcRequest.from_dict(body)

            # Streaming methods
            if rpc_request.method in ("message/stream", "SendStreamingMessage", "tasks/sendSubscribe"):
                return EventSourceResponse(
                    stream_send_message(rpc_request),
                    media_type="text/event-stream",
                )

            # Non-streaming methods
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

    # REST-style endpoints per A2A v1 HTTP binding
    @app.post("/message:send")
    async def rest_send_message(request: Request):
        """REST binding for SendMessage."""
        body = await request.json()
        rpc_request = JsonRpcRequest(
            jsonrpc="2.0",
            id=str(uuid.uuid4()),
            method="SendMessage",
            params=body,
        )
        response = await handle_rpc_request(rpc_request)
        return JSONResponse(content=response.to_dict())

    @app.post("/message:stream")
    async def rest_stream_message(request: Request):
        """REST binding for SendStreamingMessage."""
        body = await request.json()
        rpc_request = JsonRpcRequest(
            jsonrpc="2.0",
            id=str(uuid.uuid4()),
            method="SendStreamingMessage",
            params=body,
        )
        return EventSourceResponse(
            stream_send_message(rpc_request),
            media_type="text/event-stream",
        )

    @app.get("/.well-known/agent.json")
    async def get_agent_card():
        """Return the Agent Card for A2A discovery."""
        return AGENT_CARD.to_dict()

    @app.get("/.well-known/agent-card.json")
    async def get_agent_card_v2():
        """Return the Agent Card at the AgentCore-expected path."""
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
    """Handle a non-streaming JSON-RPC request and return a response."""
    method_handlers = {
        # A2A v1 JSON-RPC method names
        "message/send": handle_send_message,
        "tasks/get": handle_get_task,
        "tasks/cancel": handle_cancel_task,
        # gRPC/PascalCase aliases
        "SendMessage": handle_send_message,
        "GetTask": handle_get_task,
        "CancelTask": handle_cancel_task,
        # Legacy method names
        "tasks/send": handle_send_message,
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


async def handle_send_message(request: JsonRpcRequest) -> JsonRpcResponse:
    """Handle SendMessage - process a workout request and return a Task."""
    params = request.params
    message = extract_message_from_params(params)

    task_id = str(uuid.uuid4())
    context_id = message.context_id or str(uuid.uuid4())

    task = Task(
        id=task_id,
        context_id=context_id,
        status=TaskStatus(state=TaskState.WORKING),
        history=[message],
    )
    tasks[task_id] = task

    message_text = message.get_text()

    try:
        loop = asyncio.get_event_loop()
        parts, artifacts = await loop.run_in_executor(
            None, run_agent_and_build_result, message_text, task_id, context_id,
        )

        task.status = TaskStatus(state=TaskState.COMPLETED)
        task.artifacts = artifacts
        task.history.append(Message(
            role="agent",
            parts=parts,
            context_id=context_id,
            task_id=task_id,
        ))
        tasks[task_id] = task

        return JsonRpcResponse(
            jsonrpc="2.0",
            id=request.id,
            result=task.to_dict(),
        )

    except Exception as e:
        error_type = type(e).__name__
        error_message = str(e)
        error_tb = traceback.format_exc()
        print(f"ERROR in orchestrator: {error_type}: {error_message}")
        print(f"Traceback:\n{error_tb}")

        task.status = TaskStatus(
            state=TaskState.FAILED,
            message=Message(
                role="agent",
                parts=[Part(kind="text", text=f"{error_type}: {error_message}")],
            ),
        )
        tasks[task_id] = task

        return JsonRpcResponse(
            jsonrpc="2.0",
            id=request.id,
            result=task.to_dict(),
        )


async def handle_get_task(request: JsonRpcRequest) -> JsonRpcResponse:
    """Handle GetTask - retrieve task status."""
    task_id = request.params.get("id") or request.params.get("taskId")
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
        result=task.to_dict(),
    )


async def handle_cancel_task(request: JsonRpcRequest) -> JsonRpcResponse:
    """Handle CancelTask - cancel a running task."""
    task_id = request.params.get("id") or request.params.get("taskId")
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

    task.status = TaskStatus(state=TaskState.CANCELED)
    tasks[task_id] = task

    return JsonRpcResponse(
        jsonrpc="2.0",
        id=request.id,
        result=task.to_dict(),
    )


def _sse_event(request_id: str, result_obj: dict[str, Any]) -> dict[str, str]:
    """Build an SSE event dict with a JSON-RPC response wrapping the result."""
    return {
        "data": json.dumps(JsonRpcResponse(
            jsonrpc="2.0",
            id=request_id,
            result=result_obj,
        ).to_dict()),
    }


async def stream_send_message(request: JsonRpcRequest):
    """Stream task execution via SSE per A2A v1 spec.

    Each SSE event data is a JSON-RPC response where `result` is one of the
    typed objects with a `kind` discriminator: status-update, artifact-update,
    message, or task.
    """
    params = request.params
    message = extract_message_from_params(params)

    task_id = str(uuid.uuid4())
    context_id = message.context_id or str(uuid.uuid4())

    task = Task(
        id=task_id,
        context_id=context_id,
        status=TaskStatus(state=TaskState.SUBMITTED),
        history=[message],
    )
    tasks[task_id] = task

    # Send initial status: submitted
    yield _sse_event(request.id, TaskStatusUpdateEvent(
        task_id=task_id, context_id=context_id,
        status=TaskStatus(state=TaskState.SUBMITTED), final=False,
    ).to_dict())

    # Send working status
    task.status = TaskStatus(state=TaskState.WORKING)
    tasks[task_id] = task

    yield _sse_event(request.id, TaskStatusUpdateEvent(
        task_id=task_id, context_id=context_id,
        status=TaskStatus(
            state=TaskState.WORKING,
            message=Message(role="agent", parts=[Part(kind="text", text="Processing your workout request...")]),
        ),
        final=False,
    ).to_dict())

    message_text = message.get_text()

    try:
        loop = asyncio.get_event_loop()
        parts, artifacts = await loop.run_in_executor(
            None, run_agent_and_build_result, message_text, task_id, context_id,
        )

        # Send artifact updates
        for artifact in artifacts:
            yield _sse_event(request.id, TaskArtifactUpdateEvent(
                task_id=task_id, context_id=context_id,
                artifact=artifact, last_chunk=True,
            ).to_dict())

        # Send the agent message (clients extract the response from this)
        agent_message = Message(
            role="agent", parts=parts,
            context_id=context_id, task_id=task_id,
        )
        yield _sse_event(request.id, agent_message.to_dict())

        # Update task to completed and send final task
        task.status = TaskStatus(state=TaskState.COMPLETED)
        task.artifacts = artifacts
        task.history.append(agent_message)
        tasks[task_id] = task

        yield _sse_event(request.id, task.to_dict())

    except Exception as e:
        error_type = type(e).__name__
        error_message = str(e)
        print(f"ERROR in orchestrator streaming: {error_type}: {error_message}")
        print(f"Traceback:\n{traceback.format_exc()}")

        error_msg = Message(
            role="agent", parts=[Part(kind="text", text=f"{error_type}: {error_message}")],
            context_id=context_id, task_id=task_id,
        )
        yield _sse_event(request.id, error_msg.to_dict())

        task.status = TaskStatus(state=TaskState.FAILED, message=error_msg)
        tasks[task_id] = task

        yield _sse_event(request.id, task.to_dict())
