"""Life Sync Agent - LangGraph Implementation.

A pragmatic logistics and lifestyle coordinator that validates
workout plans against real-world constraints.
"""

import json
from dataclasses import dataclass
from typing import Any, AsyncGenerator

from langchain_aws import ChatBedrockConverse
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from tools import get_calendar_availability, get_equipment_inventory, check_equipment_for_workout

SYSTEM_PROMPT = """You are a pragmatic logistics and lifestyle coordinator.

Objective: Validate plans against the user's real-world constraints:
time, equipment, and fatigue.

Instructions:
1. When the Orchestrator sends a proposed workout plan, check it against the user's schedule
2. Use get_calendar_availability to check if the user has enough free time
3. Use get_equipment_inventory or check_equipment_for_workout to verify equipment availability
4. Explicitly flag any conflicts found

Types of conflicts to check for:
- TIME: "user only has a 30-minute gap" or "no free time today"
- EQUIPMENT: "current location has no barbell" or "missing squat rack"
- Both conflicts may exist simultaneously

Your response should always include a structured analysis in this format:
{
  "analysis": {
    "hasConflicts": true/false,
    "conflicts": [
      {
        "type": "time" or "equipment",
        "severity": "high", "medium", or "low",
        "message": "Description of the conflict",
        "suggestion": "How to resolve or work around it"
      }
    ],
    "recommendation": "Overall recommendation for the Orchestrator"
  }
}

Tone: Empathetic, realistic, and brief."""


def create_life_sync_agent():
    """Create the Life Sync LangGraph agent."""
    model = ChatBedrockConverse(
        model=os.environ.get("MODEL_ID", "us.amazon.nova-lite-v1:0"),
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
        max_tokens=2000,
        temperature=0.3,
    )

    tools = [
        get_calendar_availability,
        get_equipment_inventory,
        check_equipment_for_workout,
    ]

    agent = create_react_agent(
        model,
        tools,
    )

    return agent


import os


@dataclass
class WorkoutPlan:
    """A workout plan to validate."""
    name: str
    estimated_duration: int
    exercises: list[dict[str, Any]]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkoutPlan":
        return cls(
            name=data.get("name", "Unnamed Workout"),
            estimated_duration=data.get("estimatedDuration", 60),
            exercises=data.get("exercises", []),
        )


@dataclass
class ConflictAnalysis:
    """Analysis of conflicts for a workout plan."""
    has_conflicts: bool
    conflicts: list[dict[str, Any]]
    recommendation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "analysis": {
                "hasConflicts": self.has_conflicts,
                "conflicts": self.conflicts,
                "recommendation": self.recommendation,
            }
        }


async def validate_workout(
    workout_plan: WorkoutPlan | None = None,
    raw_request: str | None = None,
    date: str | None = None,
    location: str | None = None,
) -> ConflictAnalysis:
    """Validate a workout plan against user constraints.

    Args:
        workout_plan: The structured workout plan to validate.
        raw_request: Raw text request if no structured plan.
        date: Date to check availability (YYYY-MM-DD).
        location: Location to check equipment.

    Returns:
        ConflictAnalysis with any detected conflicts.
    """
    agent = create_life_sync_agent()

    # Build the validation prompt
    if workout_plan:
        required_equipment = set()
        for exercise in workout_plan.exercises:
            for eq in exercise.get("equipment", []):
                required_equipment.add(eq)

        prompt = f"""Please validate this workout plan:

Workout: {workout_plan.name}
Duration: {workout_plan.estimated_duration} minutes
Exercises: {len(workout_plan.exercises)} exercises
Required Equipment: {', '.join(required_equipment) if required_equipment else 'None (bodyweight)'}

1. Check if the user has {workout_plan.estimated_duration} minutes available today
2. Check if all required equipment is available at their location ({location or 'home'})
3. Report any conflicts found

Return a structured analysis with hasConflicts, conflicts array, and recommendation."""
    else:
        prompt = raw_request or "Check my availability for a 60-minute workout today."

    # Run the agent
    result = await agent.ainvoke({
        "messages": [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ],
    })

    # Extract the response
    last_message = result["messages"][-1]
    response_text = ""
    if isinstance(last_message, AIMessage):
        if isinstance(last_message.content, str):
            response_text = last_message.content
        elif isinstance(last_message.content, list):
            response_text = " ".join(
                part.get("text", "") for part in last_message.content
                if isinstance(part, dict) and part.get("type") == "text"
            )

    # Parse the analysis from the response
    try:
        json_match = None
        # Try to find JSON in the response
        import re
        json_pattern = r'\{[\s\S]*"analysis"[\s\S]*\}'
        match = re.search(json_pattern, response_text)
        if match:
            parsed = json.loads(match.group())
            analysis = parsed.get("analysis", {})
            return ConflictAnalysis(
                has_conflicts=analysis.get("hasConflicts", False),
                conflicts=analysis.get("conflicts", []),
                recommendation=analysis.get("recommendation", response_text),
            )
    except json.JSONDecodeError:
        pass

    # Fallback: Parse from text
    has_conflicts = any(
        word in response_text.lower()
        for word in ["conflict", "missing", "unavailable", "no time", "limited"]
    )

    return ConflictAnalysis(
        has_conflicts=has_conflicts,
        conflicts=[],
        recommendation=response_text,
    )


async def stream_validation(
    workout_plan: WorkoutPlan | None = None,
    raw_request: str | None = None,
) -> AsyncGenerator[str, None]:
    """Stream the validation process.

    Yields chunks of the validation response.
    """
    agent = create_life_sync_agent()

    if workout_plan:
        prompt = f"Validate this workout: {workout_plan.name} ({workout_plan.estimated_duration} min)"
    else:
        prompt = raw_request or "Check my availability for a workout."

    async for event in agent.astream_events(
        {
            "messages": [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ],
        },
        version="v2",
    ):
        if event["event"] == "on_chat_model_stream":
            chunk = event["data"].get("chunk")
            if chunk and hasattr(chunk, "content"):
                content = chunk.content
                if isinstance(content, str):
                    yield content
                elif isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "text":
                            yield part.get("text", "")
