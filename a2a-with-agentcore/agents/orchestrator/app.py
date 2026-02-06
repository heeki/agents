"""Orchestrator Agent - Main Entry Point.

A2A-compliant coordinator agent for the fitness multi-agent system.
"""

import os
import sys

# Add the agent directory to the path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from a2a.server import create_a2a_app

PORT = int(os.environ.get("ORCHESTRATOR_PORT", "8081"))


def main():
    """Run the Orchestrator agent server."""
    app = create_a2a_app()

    print(f"Orchestrator Agent running on port {PORT}")
    print(f"A2A Endpoint: http://localhost:{PORT}/")
    print(f"Agent Card: http://localhost:{PORT}/.well-known/agent.json")
    print(f"Health Check: http://localhost:{PORT}/health")

    uvicorn.run(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()
