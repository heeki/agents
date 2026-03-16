import argparse
import base64
import json
import sys

import boto3
import requests


# One test invocation per tool with representative arguments.
TOOL_TEST_CASES: list[tuple[str, dict]] = [
    ("hello_world",         {"name": "World"}),
    ("fetch_webpage",       {"url": "https://example.com"}),
    ("geocode_location",    {"address": "Seattle, WA"}),
    ("reverse_geocode",     {"latitude": 47.6062, "longitude": -122.3321}),
    ("get_weather",         {"city": "Seattle"}),
    ("get_exchange_rate",   {"base_currency": "USD", "target_currency": "EUR"}),
    ("get_ip_info",         {"ip_address": "8.8.8.8"}),
    ("web_search",          {"query": "Python programming"}),
    ("get_current_time",    {"timezone_name": "UTC"}),
    ("calculate_math",      {"expression": "sqrt(144) + 2**8"}),
    ("get_public_holidays", {"country_code": "US", "year": 2024}),
]


def get_jwt_token(region: str, cognito_domain: str, client_id: str, client_secret: str, scope: str) -> str:
    """Get JWT access token from Cognito using client_credentials flow."""
    token_url = f"https://{cognito_domain}.auth.{region}.amazoncognito.com/oauth2/token"
    auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    r = requests.post(token_url, data={
        "grant_type": "client_credentials",
        "scope": scope,
    }, headers={
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/x-www-form-urlencoded",
    })
    r.raise_for_status()
    return r.json()["access_token"]


def get_user_token(region: str, user_client_id: str, username: str, password: str) -> str:
    """Get JWT access token from Cognito using USER_PASSWORD_AUTH flow."""
    cognito = boto3.client("cognito-idp", region_name=region)
    resp = cognito.initiate_auth(
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={
            "USERNAME": username,
            "PASSWORD": password,
        },
        ClientId=user_client_id,
    )
    return resp["AuthenticationResult"]["AccessToken"]


def send_rpc(url: str, rpc_id: int, method: str, token: str, params: dict | None = None,
             session_id: str | None = None, allow_error_status: bool = False) -> tuple[str, dict, dict]:
    payload: dict = {"jsonrpc": "2.0", "id": rpc_id, "method": method}
    if params:
        payload["params"] = params
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Authorization": f"Bearer {token}",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    r = requests.post(url, json=payload, headers=headers, timeout=60)
    if not allow_error_status:
        r.raise_for_status()
    sid = r.headers.get("Mcp-Session-Id", session_id or "")
    resp_headers = dict(r.headers)
    body = r.text
    # Gateway may return a 4xx with a JSON-RPC error body (not SSE-wrapped).
    if r.status_code >= 400:
        try:
            return sid, json.loads(body), resp_headers
        except Exception:
            return sid, {"error": {"code": r.status_code, "message": body}}, resp_headers
    for line in body.strip().splitlines():
        if line.startswith("data: "):
            return sid, json.loads(line[6:]), resp_headers
    return sid, json.loads(body), resp_headers


def run_initialize(url: str, token: str, label: str) -> tuple[str, list[dict]]:
    """Run initialize + tools/list. Returns (session_id, tools)."""
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")

    print("\n--- initialize ---")
    session_id, data, _ = send_rpc(url, 1, "initialize", token, {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "test-client", "version": "1.0"},
    })
    print(f"Session: {session_id}")
    print(f"Server: {data.get('result', {}).get('serverInfo', {})}")

    print("\n--- tools/list ---")
    _, data, _ = send_rpc(url, 2, "tools/list", token, session_id=session_id)
    tools = data.get("result", {}).get("tools", [])
    tool_names = [t["name"] for t in tools]
    for name in tool_names:
        print(f"  - {name}")
    print(f"  ({len(tool_names)} tools listed)")
    return session_id, tools


def run_all_tools(url: str, token: str, session_id: str, tools: list[dict]) -> None:
    """Call every tool and assert no errors."""
    tool_map = {t["name"]: t for t in tools}
    errors: list[str] = []

    for tool_name, args in TOOL_TEST_CASES:
        qualified = next((n for n in tool_map if n == tool_name or n.endswith(f"___{tool_name}")), None)
        if qualified is None:
            errors.append(f"{tool_name}: not found in tools/list")
            continue
        print(f"\n--- tools/call {tool_name} ---")
        _, data, resp_headers = send_rpc(url, 10, "tools/call", token, {
            "name": qualified,
            "arguments": args,
        }, session_id=session_id)
        if "error" in data:
            errors.append(f"{tool_name}: {data['error']}")
            print(f"  ERROR: {data['error']}")
        elif data.get("result", {}).get("isError"):
            msg = data["result"].get("content", [{}])[0].get("text", "unknown")
            print(f"  (tool returned error: {msg})")
        else:
            content = data.get("result", {}).get("content", [])
            preview = content[0].get("text", "")[:120] if content else ""
            interceptor_hdr = resp_headers.get("x-amzn-bedrock-agentcore-runtime-custom-interceptor-demo", "")
            print(f"  OK: {preview}")
            if interceptor_hdr:
                print(f"  interceptor-header: {interceptor_hdr}")

    if errors:
        print(f"\nFAILED: {len(errors)} tool(s) errored:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print(f"\nAll {len(TOOL_TEST_CASES)} tools passed.")


def run_permission_test(url: str, token: str, session_id: str, tools: list[dict], expect_invoke_denied: bool) -> None:
    """Call hello_world and assert allow/deny behaviour matches expectation."""
    tool_map = {t["name"]: t for t in tools}
    qualified = next((n for n in tool_map if n == "hello_world" or n.endswith("___hello_world")), None)
    if qualified is None:
        print("  hello_world not found in tools/list — FAILED")
        sys.exit(1)

    print(f"\n--- tools/call hello_world (expect {'DENIED' if expect_invoke_denied else 'ALLOWED'}) ---")
    _, data, _ = send_rpc(url, 3, "tools/call", token, {
        "name": qualified,
        "arguments": {"name": "World"},
    }, session_id=session_id, allow_error_status=expect_invoke_denied)

    if expect_invoke_denied:
        # Accept: top-level JSON-RPC error (HTTP 4xx) or tool-level isError response (HTTP 200
        # with the Gateway's "InterceptorException" wrapping the blocked interceptor reply).
        if "error" in data:
            print(f"  DENIED as expected: {data['error'].get('message', data['error'])}")
        elif data.get("result", {}).get("isError"):
            msg = data["result"].get("content", [{}])[0].get("text", "unknown")
            print(f"  DENIED as expected (interceptor blocked): {msg}")
        else:
            print(f"  UNEXPECTED SUCCESS — should have been denied: {data}")
            sys.exit(1)
    else:
        if "error" in data:
            print(f"  UNEXPECTED DENIAL — should have been allowed: {data['error']}")
            sys.exit(1)
        if data.get("result", {}).get("isError"):
            msg = data["result"].get("content", [{}])[0].get("text", "unknown")
            print(f"  UNEXPECTED DENIAL — should have been allowed: {msg}")
            sys.exit(1)
        content = data.get("result", {}).get("content", [])
        preview = content[0].get("text", "")[:200] if content else str(data)
        print(f"  ALLOWED as expected: {preview}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Test MCP server through AgentCore Gateway")
    parser.add_argument("gateway_url", help="AgentCore Gateway MCP endpoint URL")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument("--cognito-domain", required=True, help="Cognito UserPool domain prefix")
    parser.add_argument("--cognito-user-pool-id", required=True, help="Cognito UserPool ID")
    parser.add_argument("--cognito-client-id", required=True, help="Cognito M2M App Client ID")
    parser.add_argument("--scope", default="", help="OAuth scope (for client_credentials mode)")
    parser.add_argument("--user-client-id", default="", help="Cognito User Client ID (for USER_PASSWORD_AUTH mode)")
    parser.add_argument("--username", default="", help="Cognito username (for USER_PASSWORD_AUTH mode)")
    parser.add_argument("--password", default="", help="Cognito password (for USER_PASSWORD_AUTH mode)")
    parser.add_argument("--all-tools", action="store_true", help="Call every tool (not just hello_world)")
    parser.add_argument("--expect-invoke-denied", action="store_true",
                        help="Expect tools/call to be denied (for demo-admins users)")
    args = parser.parse_args()

    # Acquire token
    if args.username and args.password:
        user_client_id = args.user_client_id or args.cognito_client_id
        token = get_user_token(args.region, user_client_id, args.username, args.password)
        label = f"USER_PASSWORD_AUTH  user={args.username}"
        print(f"Using JWT Bearer token auth ({label})")
    else:
        cognito = boto3.client("cognito-idp", region_name=args.region)
        resp = cognito.describe_user_pool_client(UserPoolId=args.cognito_user_pool_id, ClientId=args.cognito_client_id)
        client_secret = resp["UserPoolClient"]["ClientSecret"]
        token = get_jwt_token(args.region, args.cognito_domain, args.cognito_client_id, client_secret, args.scope)
        label = "client_credentials (M2M)"
        print(f"Using JWT Bearer token auth ({label})")

    session_id, tools = run_initialize(args.gateway_url, token, label)

    if args.all_tools:
        run_all_tools(args.gateway_url, token, session_id, tools)
    elif args.expect_invoke_denied:
        # Verify list succeeded (tools were returned above), then test invoke denial.
        run_permission_test(args.gateway_url, token, session_id, tools, expect_invoke_denied=True)
        print("\nPermission test passed.")
    else:
        run_permission_test(args.gateway_url, token, session_id, tools, expect_invoke_denied=False)
        print("\nAll tests passed.")


if __name__ == "__main__":
    main()
