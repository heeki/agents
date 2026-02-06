"""Life Sync Agent Tests."""

import unittest
from datetime import datetime

from src.tools.calendar import get_calendar_availability_impl
from src.tools.equipment import get_equipment_inventory_impl, check_workout_feasibility


class TestCalendarTool(unittest.TestCase):
    """Tests for the calendar availability tool."""

    def test_returns_availability_result(self):
        """Should return an AvailabilityResult object."""
        result = get_calendar_availability_impl()
        self.assertIsNotNone(result.date)
        self.assertIsInstance(result.slots, list)
        self.assertIsInstance(result.max_continuous_minutes, int)
        self.assertIsInstance(result.recommendation, str)

    def test_uses_today_when_no_date(self):
        """Should use today's date when none provided."""
        result = get_calendar_availability_impl()
        today = datetime.now().strftime("%Y-%m-%d")
        self.assertEqual(result.date, today)

    def test_respects_duration_requirement(self):
        """Should consider duration in recommendation."""
        result_short = get_calendar_availability_impl(duration_minutes=15)
        result_long = get_calendar_availability_impl(duration_minutes=120)
        # Both should have recommendations
        self.assertIn("minute", result_short.recommendation.lower())

    def test_slots_have_required_fields(self):
        """Each slot should have start, end, available, and optional conflict_reason."""
        result = get_calendar_availability_impl()
        for slot in result.slots:
            self.assertIsNotNone(slot.start)
            self.assertIsNotNone(slot.end)
            self.assertIsInstance(slot.available, bool)
            if not slot.available:
                self.assertIsNotNone(slot.conflict_reason)


class TestEquipmentTool(unittest.TestCase):
    """Tests for the equipment inventory tool."""

    def test_returns_equipment_list(self):
        """Should return an EquipmentList object."""
        result = get_equipment_inventory_impl()
        self.assertIsNotNone(result.location)
        self.assertIsInstance(result.available, list)
        self.assertIsInstance(result.missing, list)

    def test_default_location_is_home(self):
        """Should default to home location."""
        result = get_equipment_inventory_impl()
        self.assertEqual(result.location, "home")

    def test_gym_has_full_equipment(self):
        """Gym should have all equipment available."""
        result = get_equipment_inventory_impl("gym")
        self.assertEqual(result.location, "gym")
        self.assertIn("barbell", result.available)
        self.assertIn("squat_rack", result.available)
        self.assertEqual(len(result.missing), 0)

    def test_home_missing_gym_equipment(self):
        """Home should be missing heavy gym equipment."""
        result = get_equipment_inventory_impl("home")
        self.assertIn("barbell", result.missing)
        self.assertIn("squat_rack", result.missing)

    def test_handles_location_aliases(self):
        """Should normalize location aliases."""
        result = get_equipment_inventory_impl("house")
        self.assertEqual(result.location, "home")

        result = get_equipment_inventory_impl("fitness center")
        self.assertEqual(result.location, "gym")

    def test_unknown_location_defaults_to_traveling(self):
        """Unknown locations should default to minimal equipment."""
        result = get_equipment_inventory_impl("mars")
        self.assertEqual(result.location, "traveling")


class TestWorkoutFeasibility(unittest.TestCase):
    """Tests for checking workout feasibility."""

    def test_feasible_with_available_equipment(self):
        """Should be feasible when all equipment available."""
        result = check_workout_feasibility(
            ["dumbbells", "resistance_bands"],
            "home"
        )
        self.assertTrue(result["feasible"])
        self.assertEqual(len(result["missingEquipment"]), 0)

    def test_not_feasible_with_missing_equipment(self):
        """Should not be feasible when equipment missing."""
        result = check_workout_feasibility(
            ["barbell", "squat_rack"],
            "home"
        )
        self.assertFalse(result["feasible"])
        self.assertIn("barbell", result["missingEquipment"])

    def test_feasible_at_gym(self):
        """Gym should have all standard equipment."""
        result = check_workout_feasibility(
            ["barbell", "squat_rack", "cable_machine"],
            "gym"
        )
        self.assertTrue(result["feasible"])

    def test_provides_recommendation(self):
        """Should always provide a recommendation."""
        result = check_workout_feasibility(["barbell"], "home")
        self.assertIn("recommendation", result)
        self.assertIsInstance(result["recommendation"], str)


if __name__ == "__main__":
    unittest.main()
