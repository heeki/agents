import base64
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger()
logger.setLevel(logging.INFO)

CUSTOM_HEADER = "X-Amzn-Bedrock-AgentCore-Runtime-Custom-Interceptor-Demo"


def decode_jwt_payload(token: str) -> dict:
    """Decode JWT payload without verification (already validated by the Gateway authorizer)."""
    parts = token.split(".")
    if len(parts) != 3:
        return {}
    padded = parts[1] + "=" * (4 - len(parts[1]) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(padded))
    except Exception:
        return {}


def lambda_handler(event: dict, context) -> dict:
    """Request interceptor for AgentCore Gateway.

    Enforces group-based access control using Cognito JWT claims:
      - M2M tokens (client_credentials, have 'scope' but no 'cognito:groups'):
          full access to all MCP methods.
      - Users in 'demo-admins' group:
          tools/list allowed; tools/call denied with JSON-RPC 403 error.
      - Users in 'admins' or 'users' group:
          full access to all MCP methods.

    For authorized tools/call requests, injects a custom timestamp header
    to demonstrate header injection via Lambda interceptors.
    """
    logger.info("Interceptor input event: %s", json.dumps(event))

    mcp_data = event.get("mcp", {})
    gateway_request = mcp_data.get("gatewayRequest", {})
    request_body = gateway_request.get("body", {})
    headers = gateway_request.get("headers", {})
    mcp_method = request_body.get("method", "unknown")
    request_id = request_body.get("id")

    logger.info("MCP method: %s", mcp_method)

    # Decode the JWT to determine the caller's identity and permissions.
    # The Gateway has already validated the token; we just read the claims.
    auth_header = headers.get("Authorization", headers.get("authorization", ""))
    payload: dict = {}
    if auth_header.startswith("Bearer "):
        payload = decode_jwt_payload(auth_header[7:])
        logger.info(
            "JWT claims: sub=%s, groups=%s, scope=%s",
            payload.get("sub"),
            payload.get("cognito:groups"),
            payload.get("scope"),
        )

    # M2M tokens (client_credentials flow) carry a 'scope' claim but no
    # 'cognito:groups'.  User tokens carry 'cognito:groups' and no 'scope'.
    groups: list = payload.get("cognito:groups", [])
    is_m2m: bool = bool(payload.get("scope")) and "cognito:groups" not in payload

    # Enforce: demo-admins may list tools but not invoke them.
    if mcp_method == "tools/call" and not is_m2m and "demo-admins" in groups:
        logger.warning("Denying tools/call for demo-admins user (sub=%s)", payload.get("sub"))
        return {
            "interceptorOutputVersion": "1.0",
            "mcp": {
                "gatewayResponse": {
                    "statusCode": 403,
                    "body": json.dumps({
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32603,
                            "message": "Forbidden: demo-admins may list tools but not invoke them",
                        },
                    }),
                }
            },
        }

    # Build the pass-through (or enriched) response.
    response: dict = {
        "interceptorOutputVersion": "1.0",
        "mcp": {
            "transformedGatewayRequest": {
                "body": request_body,
            }
        },
    }

    # For authorized tools/call requests, inject the custom timestamp header.
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
