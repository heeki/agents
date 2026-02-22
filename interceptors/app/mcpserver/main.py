import json
import logging
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mcp = FastMCP("interceptors-demo", host="0.0.0.0", port=8000, stateless_http=True)


@mcp.tool()
def hello_world(name: str) -> dict:
    """Says hello to the given name. Used to demonstrate Gateway interceptors."""
    logger.info("hello_world invoked with name=%s", name)
    timestamp = datetime.now(timezone.utc).isoformat()
    return {"greeting": f"Hello, {name}!", "timestamp": timestamp}


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
