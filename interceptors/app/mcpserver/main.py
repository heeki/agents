import logging
import uvicorn
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP, Context

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CUSTOM_HEADER = "x-amzn-bedrock-agentcore-runtime-custom-interceptor-demo"

mcp = FastMCP("interceptors-demo", host="0.0.0.0", port=8000, stateless_http=True)


@mcp.tool()
def hello_world(name: str, ctx: Context) -> dict:
    """Says hello to the given name. Used to demonstrate Gateway interceptors."""
    timestamp = datetime.now(timezone.utc).isoformat()
    interceptor_header = None
    request = ctx.request_context.request
    if request is not None:
        interceptor_header = request.headers.get(CUSTOM_HEADER)
        logger.info("Request headers: %s", dict(request.headers))
        logger.info("Interceptor header: %s", interceptor_header)
    return {
        "greeting": f"Hello, {name}!",
        "timestamp": timestamp,
        "interceptor_header": interceptor_header,
    }


class HeaderEchoMiddleware:
    """ASGI middleware that echoes the interceptor request header back as a response header."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Extract the custom header from the request
        req_headers = dict(scope.get("headers", []))
        custom_val = req_headers.get(CUSTOM_HEADER.encode(), b"")

        async def send_with_header(message):
            if message["type"] == "http.response.start" and custom_val:
                headers = list(message.get("headers", []))
                headers.append((CUSTOM_HEADER.encode(), custom_val))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_header)


if __name__ == "__main__":
    app = mcp.streamable_http_app()
    app = HeaderEchoMiddleware(app)
    uvicorn.run(app, host="0.0.0.0", port=8000)
