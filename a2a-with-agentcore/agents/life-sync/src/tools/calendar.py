"""GetCalendarAvailability Tool - Mock Calendar Service.

Provides simulated calendar availability data for workout scheduling.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
import random
from typing import Any

from langchain_core.tools import tool


@dataclass
class TimeSlot:
    """A time slot with availability information."""
    start: str  # ISO 8601 format
    end: str    # ISO 8601 format
    available: bool
    conflict_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "start": self.start,
            "end": self.end,
            "available": self.available,
            "conflictReason": self.conflict_reason,
        }


@dataclass
class AvailabilityResult:
    """Result of a calendar availability check."""
    date: str
    slots: list[TimeSlot]
    max_continuous_minutes: int
    recommendation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "slots": [s.to_dict() for s in self.slots],
            "maxContinuousMinutes": self.max_continuous_minutes,
            "recommendation": self.recommendation,
        }


# Mock calendar data - simulates a busy professional's schedule
MOCK_SCHEDULES = {
    "busy_day": [
        TimeSlot("08:00", "09:00", False, "Team standup"),
        TimeSlot("09:00", "10:00", True, None),
        TimeSlot("10:00", "12:00", False, "Client meeting"),
        TimeSlot("12:00", "13:00", False, "Lunch with colleague"),
        TimeSlot("13:00", "15:00", False, "Project review"),
        TimeSlot("15:00", "15:30", True, None),
        TimeSlot("15:30", "17:00", False, "Sprint planning"),
        TimeSlot("17:00", "17:30", True, None),
        TimeSlot("17:30", "18:00", False, "Commute"),
        TimeSlot("18:00", "18:30", True, None),
        TimeSlot("18:30", "19:30", False, "Dinner"),
        TimeSlot("19:30", "21:00", True, None),
    ],
    "moderate_day": [
        TimeSlot("06:00", "07:00", True, None),
        TimeSlot("07:00", "08:00", False, "Get ready for work"),
        TimeSlot("08:00", "09:00", False, "Commute"),
        TimeSlot("09:00", "12:00", False, "Work block"),
        TimeSlot("12:00", "13:00", True, None),
        TimeSlot("13:00", "17:00", False, "Work block"),
        TimeSlot("17:00", "18:00", True, None),
        TimeSlot("18:00", "19:00", True, None),
        TimeSlot("19:00", "20:00", False, "Family time"),
        TimeSlot("20:00", "21:30", True, None),
    ],
    "light_day": [
        TimeSlot("06:00", "08:00", True, None),
        TimeSlot("08:00", "09:00", False, "Morning routine"),
        TimeSlot("09:00", "10:00", True, None),
        TimeSlot("10:00", "11:00", False, "Quick call"),
        TimeSlot("11:00", "14:00", True, None),
        TimeSlot("14:00", "15:00", False, "Appointment"),
        TimeSlot("15:00", "21:00", True, None),
    ],
}


def get_calendar_availability_impl(
    date: str | None = None,
    duration_minutes: int = 60,
) -> AvailabilityResult:
    """Check calendar availability for a given date and duration.

    Args:
        date: The date to check (YYYY-MM-DD format). Defaults to today.
        duration_minutes: Required workout duration in minutes.

    Returns:
        AvailabilityResult with available slots and recommendations.
    """
    # Use today if no date provided
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    # Deterministically select schedule based on date hash
    schedule_names = list(MOCK_SCHEDULES.keys())
    schedule_index = hash(date) % len(schedule_names)
    schedule_name = schedule_names[schedule_index]
    slots = MOCK_SCHEDULES[schedule_name]

    # Find max continuous available time
    max_continuous = 0
    current_continuous = 0

    for slot in slots:
        if slot.available:
            start_time = datetime.strptime(slot.start, "%H:%M")
            end_time = datetime.strptime(slot.end, "%H:%M")
            slot_duration = int((end_time - start_time).total_seconds() / 60)
            current_continuous += slot_duration
            max_continuous = max(max_continuous, current_continuous)
        else:
            current_continuous = 0

    # Generate recommendation
    if max_continuous >= duration_minutes:
        available_slots = [s for s in slots if s.available]
        suitable_slots = []
        for slot in available_slots:
            start_time = datetime.strptime(slot.start, "%H:%M")
            end_time = datetime.strptime(slot.end, "%H:%M")
            slot_duration = int((end_time - start_time).total_seconds() / 60)
            if slot_duration >= duration_minutes:
                suitable_slots.append(f"{slot.start}-{slot.end}")

        recommendation = f"You have {len(suitable_slots)} time slot(s) available for a {duration_minutes}-minute workout: {', '.join(suitable_slots)}"
    elif max_continuous >= 30:
        recommendation = f"Limited availability. Maximum continuous free time is {max_continuous} minutes. Consider a shorter workout."
    elif max_continuous >= 15:
        recommendation = f"Very limited availability. Only {max_continuous} minutes free. Consider a quick HIIT session or reschedule."
    else:
        recommendation = "No significant free time available today. Consider rescheduling the workout."

    return AvailabilityResult(
        date=date,
        slots=slots,
        max_continuous_minutes=max_continuous,
        recommendation=recommendation,
    )


@tool
def get_calendar_availability(
    date: str | None = None,
    duration_minutes: int = 60,
) -> str:
    """Check the user's calendar availability for workout scheduling.

    Use this tool to verify if the user has enough free time for a workout.
    Returns available time slots and recommendations.

    Args:
        date: The date to check in YYYY-MM-DD format. Defaults to today.
        duration_minutes: Required workout duration in minutes. Default is 60.

    Returns:
        JSON string with available time slots and a recommendation.
    """
    import json
    result = get_calendar_availability_impl(date, duration_minutes)
    return json.dumps(result.to_dict(), indent=2)
