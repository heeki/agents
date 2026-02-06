"""Life Sync Agent - Main Entry Point.

A2A-compliant agent for validating workout plans against real-world constraints.
"""

import os
import uvicorn

from a2a.server import create_a2a_app

PORT = int(os.environ.get("LIFESYNC_PORT", "8083"))


def main():
    """Run the Life Sync agent server."""
    app = create_a2a_app()

    print(f"Life Sync Agent running on port {PORT}")
    print(f"A2A Endpoint: http://localhost:{PORT}/")
    print(f"Agent Card: http://localhost:{PORT}/.well-known/agent.json")
    print(f"Health Check: http://localhost:{PORT}/health")

    uvicorn.run(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()
