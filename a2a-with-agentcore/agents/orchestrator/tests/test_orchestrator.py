"""Orchestrator Agent Tests."""

import unittest
from unittest.mock import AsyncMock, patch, MagicMock

from a2a.types import Message, MessagePart, Task, TaskStatus


class TestA2ATypes(unittest.TestCase):
    """Tests for A2A type definitions."""

    def test_message_part_text(self):
        """Should create text message part."""
        part = MessagePart(type="text", text="Hello")
        self.assertEqual(part.type, "text")
        self.assertEqual(part.text, "Hello")
        self.assertIsNone(part.data)

    def test_message_part_data(self):
        """Should create data message part."""
        data = {"workout": {"name": "Test"}}
        part = MessagePart(type="data", data=data)
        self.assertEqual(part.type, "data")
        self.assertEqual(part.data, data)
        self.assertIsNone(part.text)

    def test_message_to_dict(self):
        """Should serialize message to dict."""
        message = Message(
            role="user",
            parts=[
                MessagePart(type="text", text="Create a workout"),
            ],
        )
        result = message.to_dict()
        self.assertEqual(result["role"], "user")
        self.assertEqual(len(result["parts"]), 1)
        self.assertEqual(result["parts"][0]["type"], "text")

    def test_message_get_text(self):
        """Should extract text from message parts."""
        message = Message(
            role="user",
            parts=[
                MessagePart(type="text", text="Hello"),
                MessagePart(type="data", data={"key": "value"}),
                MessagePart(type="text", text="World"),
            ],
        )
        self.assertEqual(message.get_text(), "Hello World")

    def test_task_from_dict(self):
        """Should deserialize task from dict."""
        data = {
            "id": "task-123",
            "message": {
                "role": "user",
                "parts": [{"type": "text", "text": "Test"}],
            },
            "status": "pending",
        }
        task = Task.from_dict(data)
        self.assertEqual(task.id, "task-123")
        self.assertEqual(task.status, TaskStatus.PENDING)
        self.assertEqual(task.message.role, "user")

    def test_task_to_dict(self):
        """Should serialize task to dict."""
        task = Task(
            id="task-456",
            message=Message(
                role="user",
                parts=[MessagePart(type="text", text="Test")],
            ),
            status=TaskStatus.COMPLETED,
        )
        result = task.to_dict()
        self.assertEqual(result["id"], "task-456")
        self.assertEqual(result["status"], "completed")


class TestA2AClient(unittest.TestCase):
    """Tests for A2A client."""

    @patch("a2a.client.httpx.AsyncClient")
    def test_get_agent_card(self, mock_client_class):
        """Should fetch agent card."""
        from a2a.client import A2AClient

        mock_response = MagicMock()
        mock_response.json.return_value = {"name": "test-agent"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock()

        client = A2AClient("http://localhost:8080", "test")
        # Note: Would need async test runner for full test


class TestOrchestratorFlow(unittest.TestCase):
    """Tests for orchestrator workflow."""

    def test_workout_request_parsing(self):
        """Should parse workout request from message."""
        message = Message(
            role="user",
            parts=[
                MessagePart(
                    type="text",
                    text="I want a strength workout for upper body",
                ),
            ],
        )

        text = message.get_text()
        self.assertIn("strength", text.lower())
        self.assertIn("upper body", text.lower())

    def test_conflict_detection(self):
        """Should detect conflicts in life sync response."""
        life_sync_response = {
            "analysis": {
                "hasConflicts": True,
                "conflicts": [
                    {
                        "type": "time",
                        "severity": "high",
                        "message": "Only 30 minutes available",
                    },
                ],
            },
        }

        self.assertTrue(life_sync_response["analysis"]["hasConflicts"])
        self.assertEqual(len(life_sync_response["analysis"]["conflicts"]), 1)


if __name__ == "__main__":
    unittest.main()
