"""GetEquipmentInventory Tool - Mock Equipment Service.

Provides simulated equipment availability data for workout planning.
"""

from dataclasses import dataclass
from typing import Any

from langchain_core.tools import tool


@dataclass
class EquipmentList:
    """Equipment available at a location."""
    location: str
    available: list[str]
    missing: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "location": self.location,
            "available": self.available,
            "missing": self.missing,
        }


# Mock equipment data for different locations
LOCATION_EQUIPMENT = {
    "home": {
        "available": [
            "dumbbells",
            "resistance_bands",
            "pullup_bar",
            "yoga_mat",
            "foam_roller",
        ],
        "missing": [
            "barbell",
            "squat_rack",
            "bench",
            "cable_machine",
            "leg_press",
            "smith_machine",
        ],
    },
    "gym": {
        "available": [
            "barbell",
            "dumbbells",
            "squat_rack",
            "bench",
            "cable_machine",
            "leg_press",
            "pullup_bar",
            "dip_bars",
            "smith_machine",
            "rowing_machine",
            "treadmill",
            "resistance_bands",
        ],
        "missing": [],
    },
    "hotel": {
        "available": [
            "dumbbells",
            "treadmill",
            "stationary_bike",
            "yoga_mat",
        ],
        "missing": [
            "barbell",
            "squat_rack",
            "bench",
            "cable_machine",
            "pullup_bar",
            "dip_bars",
        ],
    },
    "office": {
        "available": [
            "resistance_bands",
            "yoga_mat",
        ],
        "missing": [
            "barbell",
            "dumbbells",
            "squat_rack",
            "bench",
            "cable_machine",
            "pullup_bar",
        ],
    },
    "park": {
        "available": [
            "pullup_bar",
            "dip_bars",
            "bench",
        ],
        "missing": [
            "barbell",
            "dumbbells",
            "cable_machine",
            "squat_rack",
            "resistance_bands",
        ],
    },
    "traveling": {
        "available": [
            "resistance_bands",
        ],
        "missing": [
            "barbell",
            "dumbbells",
            "squat_rack",
            "bench",
            "cable_machine",
            "pullup_bar",
        ],
    },
}

# Default current location (can be overridden)
CURRENT_LOCATION = "home"


def get_equipment_inventory_impl(
    location: str | None = None,
) -> EquipmentList:
    """Get equipment available at a specific location.

    Args:
        location: The location to check. Options: home, gym, hotel, office, park, traveling.
                  Defaults to current location (home).

    Returns:
        EquipmentList with available and missing equipment.
    """
    loc = (location or CURRENT_LOCATION).lower().strip()

    # Normalize location names
    location_aliases = {
        "house": "home",
        "apartment": "home",
        "fitness center": "gym",
        "fitness_center": "gym",
        "work": "office",
        "workplace": "office",
        "outdoor": "park",
        "outdoors": "park",
        "travel": "traveling",
        "on the road": "traveling",
    }
    loc = location_aliases.get(loc, loc)

    if loc not in LOCATION_EQUIPMENT:
        # Unknown location - assume minimal equipment (like traveling)
        loc = "traveling"

    equipment = LOCATION_EQUIPMENT[loc]
    return EquipmentList(
        location=loc,
        available=equipment["available"],
        missing=equipment["missing"],
    )


def check_workout_feasibility(
    required_equipment: list[str],
    location: str | None = None,
) -> dict[str, Any]:
    """Check if a workout is feasible with available equipment.

    Args:
        required_equipment: List of equipment needed for the workout.
        location: Location to check. Defaults to current location.

    Returns:
        Dictionary with feasibility status and missing equipment.
    """
    inventory = get_equipment_inventory_impl(location)
    available_set = set(e.lower() for e in inventory.available)

    missing = []
    for eq in required_equipment:
        eq_lower = eq.lower().replace(" ", "_")
        if eq_lower not in available_set:
            missing.append(eq)

    return {
        "feasible": len(missing) == 0,
        "location": inventory.location,
        "availableEquipment": inventory.available,
        "missingEquipment": missing,
        "recommendation": (
            "All required equipment is available."
            if len(missing) == 0
            else f"Missing equipment: {', '.join(missing)}. Consider alternatives or a different location."
        ),
    }


@tool
def get_equipment_inventory(
    location: str | None = None,
) -> str:
    """Get the equipment available at a specific location.

    Use this tool to check what fitness equipment is available at the user's
    current or specified location.

    Args:
        location: The location to check. Options: home, gym, hotel, office, park, traveling.
                  Defaults to the user's current location (home).

    Returns:
        JSON string with available and missing equipment at the location.
    """
    import json
    result = get_equipment_inventory_impl(location)
    return json.dumps(result.to_dict(), indent=2)


@tool
def check_equipment_for_workout(
    required_equipment: list[str],
    location: str | None = None,
) -> str:
    """Check if required equipment is available for a workout.

    Use this tool to verify if a proposed workout can be done at the specified location.

    Args:
        required_equipment: List of equipment needed (e.g., ["barbell", "bench"]).
        location: Location to check. Defaults to current location.

    Returns:
        JSON string with feasibility status and any missing equipment.
    """
    import json
    result = check_workout_feasibility(required_equipment, location)
    return json.dumps(result, indent=2)
