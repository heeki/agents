#!/usr/bin/env python3
"""Integration tests for the A2A multi-agent fitness system.

These tests require all three agents to be running locally via Docker Compose.
All tests use A2A JSON-RPC requests at POST /, validating the same protocol
path used in production.

Usage:
    make local.compose.up
    make test.integration
    make local.compose.down
"""

import json
import os
import sys
import time
import unittest
from typing import Any

import httpx

# Agent URLs (local development)
ORCHESTRATOR_URL = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8081")
BIOMECHANICS_URL = os.environ.get("BIOMECHANICS_URL", "http://localhost:8082")
LIFESYNC_URL = os.environ.get("LIFESYNC_URL", "http://localhost:8083")

TIMEOUT = 60.0  # Timeout for agent responses


def wait_for_agents(timeout: float = 30.0) -> bool:
    """Wait for all agents to be healthy."""
    start_time = time.time()
    agents = [
        (ORCHESTRATOR_URL, "Orchestrator"),
        (BIOMECHANICS_URL, "Biomechanics Lab"),
        (LIFESYNC_URL, "Life Sync"),
    ]

    while time.time() - start_time < timeout:
        all_healthy = True
        for url, name in agents:
            try:
                response = httpx.get(f"{url}/health", timeout=5.0)
                if response.status_code != 200:
                    all_healthy = False
                    print(f"Waiting for {name}...")
            except Exception:
                all_healthy = False
                print(f"Waiting for {name}...")

        if all_healthy:
            print("All agents are healthy!")
            return True

        time.sleep(2)

    return False


def send_a2a_task(url: str, task_id: str, message_text: str) -> dict[str, Any]:
    """Send an A2A task to an agent at root endpoint."""
    request = {
        "jsonrpc": "2.0",
        "id": task_id,
        "method": "tasks/send",
        "params": {
            "task": {
                "id": task_id,
                "message": {
                    "role": "user",
                    "parts": [{"type": "text", "text": message_text}],
                },
            }
        },
    }

    response = httpx.post(
        f"{url}/",
        json=request,
        timeout=TIMEOUT,
    )
    return response.json()


class TestAgentCards(unittest.TestCase):
    """Test Agent Card endpoints."""

    def test_orchestrator_agent_card(self):
        """Orchestrator should return valid agent card."""
        response = httpx.get(f"{ORCHESTRATOR_URL}/.well-known/agent.json")
        self.assertEqual(response.status_code, 200)

        card = response.json()
        self.assertEqual(card["name"], "orchestrator")
        self.assertIn("capabilities", card)
        self.assertIn("skills", card)

    def test_biomechanics_agent_card(self):
        """Biomechanics Lab should return valid agent card."""
        response = httpx.get(f"{BIOMECHANICS_URL}/.well-known/agent.json")
        self.assertEqual(response.status_code, 200)

        card = response.json()
        self.assertEqual(card["name"], "biomechanics-lab")

    def test_lifesync_agent_card(self):
        """Life Sync should return valid agent card."""
        response = httpx.get(f"{LIFESYNC_URL}/.well-known/agent.json")
        self.assertEqual(response.status_code, 200)

        card = response.json()
        self.assertEqual(card["name"], "life-sync")


class TestBiomechanicsLab(unittest.TestCase):
    """Test Biomechanics Lab agent directly."""

    def test_create_upper_body_workout(self):
        """Should create an upper body workout."""
        result = send_a2a_task(
            BIOMECHANICS_URL,
            "test-workout-1",
            "Create a 45-minute upper body hypertrophy workout",
        )

        self.assertIn("result", result)
        self.assertEqual(result["result"]["status"], "completed")

    def test_create_bodyweight_workout(self):
        """Should create a bodyweight workout."""
        result = send_a2a_task(
            BIOMECHANICS_URL,
            "test-workout-2",
            "Create a 20-minute bodyweight workout with no equipment",
        )

        self.assertIn("result", result)
        self.assertEqual(result["result"]["status"], "completed")


class TestLifeSync(unittest.TestCase):
    """Test Life Sync agent directly."""

    def test_check_availability(self):
        """Should check calendar availability."""
        result = send_a2a_task(
            LIFESYNC_URL,
            "test-avail-1",
            "Check if I have time for a 60-minute workout today",
        )

        self.assertIn("result", result)
        self.assertEqual(result["result"]["status"], "completed")

    def test_check_equipment_at_home(self):
        """Should check equipment at home."""
        result = send_a2a_task(
            LIFESYNC_URL,
            "test-equip-1",
            "What equipment do I have at home?",
        )

        self.assertIn("result", result)
        self.assertEqual(result["result"]["status"], "completed")


class TestOrchestratorFlow(unittest.TestCase):
    """Test full orchestrator workflow."""

    def test_simple_workout_request(self):
        """Should create a workout through the full A2A flow."""
        result = send_a2a_task(
            ORCHESTRATOR_URL,
            "test-orch-1",
            "I want a strength workout for my upper body. I have an hour.",
        )

        self.assertIn("result", result)

    def test_constrained_workout_request(self):
        """Should handle constrained workout request."""
        result = send_a2a_task(
            ORCHESTRATOR_URL,
            "test-orch-2",
            "I need a workout but I only have 25 minutes and I'm at home with just dumbbells.",
        )

        self.assertIn("result", result)

    def test_method_not_found(self):
        """Should return error for unknown methods."""
        request = {
            "jsonrpc": "2.0",
            "id": "test-unknown",
            "method": "unknown/method",
            "params": {},
        }

        response = httpx.post(
            f"{ORCHESTRATOR_URL}/",
            json=request,
            timeout=TIMEOUT,
        )

        result = response.json()
        self.assertIn("error", result)
        self.assertIn("Method not found", result["error"]["message"])


class TestA2AStreaming(unittest.TestCase):
    """Test A2A streaming responses via tasks/sendSubscribe at POST /."""

    def test_biomechanics_streaming(self):
        """Should stream workout creation via root endpoint."""
        request = {
            "jsonrpc": "2.0",
            "id": "stream-test-1",
            "method": "tasks/sendSubscribe",
            "params": {
                "task": {
                    "id": "stream-test-1",
                    "message": {
                        "role": "user",
                        "parts": [{"type": "text", "text": "Create a chest workout"}],
                    },
                }
            },
        }

        events = []
        with httpx.stream(
            "POST",
            f"{BIOMECHANICS_URL}/",
            json=request,
            timeout=TIMEOUT,
        ) as response:
            for line in response.iter_lines():
                if line.startswith("data:"):
                    events.append(json.loads(line[5:]))

        # Should have at least status and result events
        self.assertGreater(len(events), 0)


def main():
    """Run integration tests."""
    print("A2A Integration Tests")
    print("=" * 50)

    # Wait for agents to be ready
    print("\nWaiting for agents to be healthy...")
    if not wait_for_agents(timeout=60.0):
        print("\nERROR: Agents not ready. Make sure to run:")
        print("  make local.compose.up")
        sys.exit(1)

    print("\nRunning tests...")
    print("=" * 50)

    # Run tests
    unittest.main(verbosity=2, exit=True)


if __name__ == "__main__":
    main()
