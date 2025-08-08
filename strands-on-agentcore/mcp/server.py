import logging
import os
from langfuse import Langfuse, observe
from typing import Dict, Any
from mcp.server.fastmcp import FastMCP

# configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s (%(name)s) [%(levelname)s] %(message)s'
)

# initialization
logger = logging.getLogger(__name__)
langfuse = Langfuse(
    host=os.getenv("LANGFUSE_HOST"),
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY")
)

# setup mcp
mcp = FastMCP("echo", host="0.0.0.0", stateless_http=True)

@mcp.tool()
@observe()
def echo(message: str) -> Dict[str, Any]:
    """
    Echo a message back to the user.
    Args:
        message: message to echo
    Returns:
        Object with the message echoed back
    """
    return {"message": message}

def main():
    mcp.run(transport='streamable-http')

if __name__ == "__main__":
    main()