"""A2A JSON-RPC Server for Orchestrator Agent.

Implements the Google A2A protocol with streaming support.
All A2A methods are handled at POST / (root endpoint).
"""

import asyncio
import json
import os
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
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

# Import the Strands agent
from strands import Agent
from strands.models import BedrockModel
from tools import call_biomechanics_lab, call_life_sync_agent, request_workout_compromise


# In-memory task store
tasks: dict[str, Task] = {}

# Agent configuration
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


def create_a2a_app() -> FastAPI:
    """Create the FastAPI application with A2A endpoints."""
    app = FastAPI(title="Orchestrator Agent - A2A Server")

    @app.get("/")
    async def root():
        """Root GET for basic health check."""
        return {"status": "healthy", "agent": "orchestrator"}

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
    """Handle tasks/send - process a workout request."""
    params = request.params
    task_data = params.get("task", {})

    task = Task.from_dict(task_data)
    task.status = TaskStatus.WORKING
    tasks[task.id] = task

    # Extract the user's request
    message_text = task.message.get_text()

    try:
        # Run the Strands agent
        agent = create_strands_agent()

        # Run in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, agent, message_text)

        # Build result message
        result_text = str(result)
        result_parts = [MessagePart(type="text", text=result_text)]

        # Extract structured JSON from the response
        import re
        # Extract content between ```json and ``` (handles nested braces correctly)
        json_match = re.search(r'```json\s*\n?(.*?)\n?```', result_text, re.DOTALL)
        if json_match:
            try:
                json_text = json_match.group(1).strip()
                structured_data = json.loads(json_text)
                result_parts.append(
                    MessagePart(type="data", data=structured_data)
                )
            except json.JSONDecodeError as e:
                # Log the error for debugging
                print(f"JSON parsing error: {e}")
                print(f"Failed to parse JSON: {json_text[:200] if len(json_text) > 200 else json_text}")
                # Continue without structured data
                pass

        # Also try to extract structured workout data from tool results
        if hasattr(result, "tool_results"):
            for tool_result in result.tool_results:
                if isinstance(tool_result, dict) and "workout" in tool_result:
                    result_parts.append(
                        MessagePart(type="data", data=tool_result)
                    )

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
        import traceback
        task.status = TaskStatus.FAILED
        tasks[task.id] = task

        # Get detailed error information
        error_type = type(e).__name__
        error_message = str(e)
        error_traceback = traceback.format_exc()

        # Log the full error for debugging
        print(f"ERROR in orchestrator: {error_type}: {error_message}")
        print(f"Traceback:\n{error_traceback}")

        # Return detailed error to user
        detailed_message = f"{error_type}: {error_message}\n\nThis error occurred while processing your workout request. "

        # Add specific guidance for common errors
        if "ValidationException" in error_type or "validation" in error_message.lower():
            detailed_message += "The issue appears to be with invalid tool parameters being passed to the AI model. Please try rephrasing your request or contact support if this persists."
        elif "tool" in error_message.lower():
            detailed_message += "There was an issue calling one of the sub-agents. Please try again or simplify your request."
        else:
            detailed_message += f"Traceback: {error_traceback[:500]}"  # Include first 500 chars of traceback

        return JsonRpcResponse(
            jsonrpc="2.0",
            id=request.id,
            error={
                "code": ErrorCode.INTERNAL_ERROR,
                "message": detailed_message,
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
            "message": "Processing your request...",
        }),
    }

    message_text = task.message.get_text()

    try:
        # Progress updates
        yield {
            "event": "task-status",
            "data": json.dumps({
                "taskId": task.id,
                "status": TaskStatus.WORKING.value,
                "message": "Consulting Biomechanics Lab for optimal workout...",
            }),
        }

        # Run the agent (streaming not fully supported with Strands tools)
        agent = create_strands_agent()

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, agent, message_text)

        yield {
            "event": "task-status",
            "data": json.dumps({
                "taskId": task.id,
                "status": TaskStatus.WORKING.value,
                "message": "Validating with Life Sync Agent...",
            }),
        }

        # Send the result
        result_text = str(result)
        yield {
            "event": "task-result",
            "data": json.dumps({
                "taskId": task.id,
                "status": TaskStatus.COMPLETED.value,
                "result": {
                    "role": "assistant",
                    "parts": [{"type": "text", "text": result_text}],
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
