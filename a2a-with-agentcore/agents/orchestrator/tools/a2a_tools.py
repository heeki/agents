"""Strands Tools for A2A Agent Communication.

These tools wrap the A2A client to allow the Strands agent to
communicate with sub-agents.
"""

import asyncio
import json
import uuid
from typing import Any

from strands import tool

from a2a.client import get_biomechanics_client, get_life_sync_client, A2AError
from a2a.types import Message, MessagePart


@tool
def call_biomechanics_lab(
    goal: str,
    equipment: list[str],
    muscle_groups: list[str],
    duration_minutes: int = 0,
    is_compromise: bool = False,
) -> dict[str, Any]:
    """Call the Biomechanics Lab agent to create a workout plan.

    Use this tool when you need to get a workout plan based on a fitness goal.
    The Biomechanics Lab agent is an expert in exercise physiology.

    Args:
        goal: The fitness goal (e.g., "upper body hypertrophy", "full body strength").
        equipment: List of available equipment. Use empty list [] for bodyweight only.
        muscle_groups: Target muscle groups. Use empty list [] for full body.
        duration_minutes: Time constraint in minutes (0 means no constraint).
        is_compromise: Set to True if this is a refinement request due to constraints.

    Returns:
        A structured workout plan with exercises, sets, reps, and rest times.
    """
    # Ensure we have valid values
    if not isinstance(equipment, list):
        equipment = []
    if not isinstance(muscle_groups, list):
        muscle_groups = []
    if duration_minutes is None or duration_minutes <= 0:
        duration_minutes = 0

    # Build the message
    text_content = f"Create a workout plan: {goal}"
    if duration_minutes:
        text_content += f" ({duration_minutes} minutes)"
    if equipment:
        text_content += f" using {', '.join(equipment)}"
    if muscle_groups:
        text_content += f" targeting {', '.join(muscle_groups)}"
    if is_compromise:
        text_content += ". This is a compromise request - prioritize intensity over duration."

    message = Message(
        role="user",
        parts=[
            MessagePart(type="text", text=text_content),
            MessagePart(
                type="data",
                data={
                    "goal": goal,
                    "constraints": {
                        "duration": duration_minutes if duration_minutes is not None else 0,
                        "equipment": equipment,
                        "muscleGroups": muscle_groups,
                    },
                    "isCompromise": is_compromise,
                },
            ),
        ],
    )

    # Call the agent
    async def make_call():
        async with get_biomechanics_client() as client:
            task_id = f"workout-{uuid.uuid4().hex[:8]}"
            result = await client.send_task(task_id, message)
            return result

    try:
        result = asyncio.get_event_loop().run_until_complete(make_call())
    except RuntimeError:
        # No event loop running, create a new one
        result = asyncio.run(make_call())

    # Extract the result
    if "result" in result:
        task_result = result["result"]
        if "result" in task_result and isinstance(task_result["result"], dict):
            # Extract message parts
            parts = task_result["result"].get("parts", [])
            for part in parts:
                if part.get("type") == "data" and "workout" in part.get("data", {}):
                    return part["data"]

        # Return the full result if we can't extract structured data
        return task_result

    return {"error": "No result from Biomechanics Lab"}


@tool
def call_life_sync_agent(
    workout_name: str,
    duration_minutes: int,
    required_equipment: list[str],
    date: str = "",
    location: str = "home",
) -> dict[str, Any]:
    """Call the Life Sync agent to validate a workout plan.

    Use this tool to check if a workout plan is feasible given the user's
    schedule and available equipment.

    Args:
        workout_name: Name of the workout being validated.
        duration_minutes: How long the workout takes.
        required_equipment: List of equipment needed. Use empty list [] for bodyweight.
        date: Date to check availability (YYYY-MM-DD format, empty means today).
        location: Location to check equipment (default: "home").

    Returns:
        Conflict analysis with any scheduling or equipment issues.
    """
    # Ensure we have valid values
    if not isinstance(required_equipment, list):
        required_equipment = []
    if not date:
        date = ""
    if not location:
        location = "home"

    # Build the message
    text_content = f"Validate this workout: {workout_name} ({duration_minutes} min)"
    if required_equipment:
        text_content += f". Equipment needed: {', '.join(required_equipment)}"

    workout_data = {
        "name": workout_name,
        "estimatedDuration": duration_minutes,
        "exercises": [],  # Exercises not needed for validation
    }

    message = Message(
        role="user",
        parts=[
            MessagePart(type="text", text=text_content),
            MessagePart(
                type="data",
                data={
                    "workout": workout_data,
                    "date": date,
                    "location": location,
                },
            ),
        ],
    )

    # Call the agent
    async def make_call():
        async with get_life_sync_client() as client:
            task_id = f"validate-{uuid.uuid4().hex[:8]}"
            result = await client.send_task(task_id, message)
            return result

    try:
        result = asyncio.get_event_loop().run_until_complete(make_call())
    except RuntimeError:
        result = asyncio.run(make_call())

    # Extract the analysis
    if "result" in result:
        task_result = result["result"]
        if "result" in task_result and isinstance(task_result["result"], dict):
            parts = task_result["result"].get("parts", [])
            for part in parts:
                if part.get("type") == "data" and "analysis" in part.get("data", {}):
                    return part["data"]

        return task_result

    return {"error": "No result from Life Sync Agent"}


@tool
def request_workout_compromise(
    original_goal: str,
    conflicts: list[dict[str, Any]],
    available_equipment: list[str],
    available_time: int = 30,
) -> dict[str, Any]:
    """Request a modified workout from Biomechanics Lab based on constraints.

    Use this tool when the Life Sync agent reports conflicts with the original
    workout plan. This will ask the Biomechanics Lab to create an alternative
    workout that works within the constraints.

    Args:
        original_goal: The original fitness goal.
        conflicts: List of conflicts from the Life Sync agent.
        available_equipment: Equipment that IS available. Use empty list [] for bodyweight.
        available_time: Maximum available time in minutes (default: 30).

    Returns:
        A modified workout plan that respects the constraints.
    """
    # Ensure we have valid values
    if not isinstance(available_equipment, list):
        available_equipment = []
    if available_time is None or available_time <= 0:
        available_time = 30
    # Build a compromise request message
    conflict_descriptions = []
    for c in conflicts:
        conflict_descriptions.append(f"- {c.get('type', 'unknown')}: {c.get('message', 'No details')}")

    text_content = f"""Create a MODIFIED workout for: {original_goal}

The original workout had conflicts:
{chr(10).join(conflict_descriptions)}

Constraints:
- Maximum time: {available_time or 30} minutes
- Available equipment: {', '.join(available_equipment) if available_equipment else 'bodyweight only'}

Please prioritize intensity over duration. Suggest alternatives that maintain training stimulus."""

    message = Message(
        role="user",
        parts=[
            MessagePart(type="text", text=text_content),
            MessagePart(
                type="data",
                data={
                    "goal": original_goal,
                    "constraints": {
                        "duration": available_time or 30,
                        "equipment": available_equipment or [],
                    },
                    "isCompromise": True,
                },
            ),
        ],
    )

    # Call the Biomechanics Lab with compromise flag
    async def make_call():
        async with get_biomechanics_client() as client:
            task_id = f"compromise-{uuid.uuid4().hex[:8]}"
            result = await client.send_task(task_id, message)
            return result

    try:
        result = asyncio.get_event_loop().run_until_complete(make_call())
    except RuntimeError:
        result = asyncio.run(make_call())

    # Extract the result
    if "result" in result:
        task_result = result["result"]
        if "result" in task_result and isinstance(task_result["result"], dict):
            parts = task_result["result"].get("parts", [])
            for part in parts:
                if part.get("type") == "data" and "workout" in part.get("data", {}):
                    return {
                        **part["data"],
                        "isCompromise": True,
                        "originalConflicts": conflicts,
                    }

        return task_result

    return {"error": "No result from Biomechanics Lab"}
