import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger()
logger.setLevel(logging.INFO)

CUSTOM_HEADER = "X-Amzn-Bedrock-AgentCore-Runtime-Custom-Interceptor-Demo"


def lambda_handler(event: dict, context) -> dict:
    """Request interceptor for AgentCore Gateway.

    On tools/call requests, adds a custom header to demonstrate
    header injection via Lambda interceptors. All other MCP methods
    pass through unchanged.
    """
    logger.info("Interceptor input event: %s", json.dumps(event))

    mcp_data = event.get("mcp", {})
    gateway_request = mcp_data.get("gatewayRequest", {})
    request_body = gateway_request.get("body", {})
    mcp_method = request_body.get("method", "unknown")

    logger.info("MCP method: %s", mcp_method)

    response: dict = {
        "interceptorOutputVersion": "1.0",
        "mcp": {
            "transformedGatewayRequest": {
                "body": request_body
            }
        }
    }

    if mcp_method == "tools/call":
        timestamp = datetime.now(timezone.utc).isoformat()
        response["mcp"]["transformedGatewayRequest"]["headers"] = {
            CUSTOM_HEADER: f"intercepted-at-{timestamp}"
        }
        logger.info("Added custom header for tools/call: %s", timestamp)
    else:
        logger.info("Passthrough for method: %s", mcp_method)

    logger.info("Interceptor output: %s", json.dumps(response))
    return response
