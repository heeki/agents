import argparse
import base64
import boto3
import json
import sys
import urllib.parse

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


def invoke_sigv4(client: boto3.client, runtime_arn: str, qualifier: str, session_id: str | None, payload: dict) -> tuple[str, str]:
    """Invoke runtime using SigV4 via the boto3 SDK (requires no JWT auth on runtime)."""
    kwargs = {
        "agentRuntimeArn": runtime_arn,
        "qualifier": qualifier,
        "payload": json.dumps(payload),
        "contentType": "application/json",
        "accept": "application/json, text/event-stream",
    }
    if session_id:
        kwargs["runtimeSessionId"] = session_id
    r = client.invoke_agent_runtime(**kwargs)
    body = r["response"].read().decode("utf-8")
    return r.get("runtimeSessionId", ""), body


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


def invoke_jwt(endpoint_url: str, token: str, session_id: str | None, payload: dict) -> tuple[str, str]:
    """Invoke runtime using JWT Bearer token (requires JWT auth on runtime)."""
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Authorization": f"Bearer {token}",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    r = requests.post(endpoint_url, json=payload, headers=headers, timeout=60)
    r.raise_for_status()
    sid = r.headers.get("Mcp-Session-Id", session_id or "")
    return sid, r.text


def parse_sse(body: str) -> dict:
    for line in body.strip().splitlines():
        if line.startswith("data: "):
            return json.loads(line[6:])
    return {}


def run_initialize(invoke, label: str) -> tuple[str, list[str]]:
    """Run initialize + tools/list. Returns (session_id, [tool_names])."""
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")

    print("\n--- initialize ---")
    session_id, body = invoke(None, {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0"},
        },
    })
    data = parse_sse(body)
    print(f"Session: {session_id}")
    print(f"Server: {data.get('result', {}).get('serverInfo', {})}")

    print("\n--- tools/list ---")
    _, body = invoke(session_id, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    data = parse_sse(body)
    tools = data.get("result", {}).get("tools", [])
    tool_names = [t["name"] for t in tools]
    for name in tool_names:
        print(f"  - {name}")
    print(f"  ({len(tool_names)} tools listed)")
    return session_id, tool_names


def run_all_tools(invoke, session_id: str, tool_names: list[str]) -> None:
    """Call every tool and assert no errors."""
    errors: list[str] = []
    for tool_name, args in TOOL_TEST_CASES:
        # Runtime uses bare names; gateway prepends a namespace prefix.
        qualified = next((n for n in tool_names if n == tool_name or n.endswith(f"___{tool_name}")), None)
        if qualified is None:
            errors.append(f"{tool_name}: not found in tools/list")
            continue
        print(f"\n--- tools/call {tool_name} ---")
        _, body = invoke(session_id, {
            "jsonrpc": "2.0", "id": 10, "method": "tools/call",
            "params": {"name": qualified, "arguments": args},
        })
        data = parse_sse(body)
        if "error" in data:
            errors.append(f"{tool_name}: {data['error']}")
            print(f"  ERROR: {data['error']}")
        elif data.get("result", {}).get("isError"):
            msg = data["result"].get("content", [{}])[0].get("text", "unknown")
            print(f"  (tool returned error: {msg})")
        else:
            content = data.get("result", {}).get("content", [])
            preview = content[0].get("text", "")[:120] if content else ""
            print(f"  OK: {preview}")
    if errors:
        print(f"\nFAILED: {len(errors)} tool(s) errored:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print(f"\nAll {len(TOOL_TEST_CASES)} tools passed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Test MCP server on AgentCore Runtime")
    parser.add_argument("runtime_arn", help="AgentCore Runtime ARN")
    parser.add_argument("--qualifier", default="DEFAULT", help="Runtime endpoint qualifier")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument("--jwt", action="store_true", help="Use JWT Bearer token auth instead of SigV4")
    parser.add_argument("--cognito-domain", default="", help="Cognito UserPool domain prefix (for JWT mode)")
    parser.add_argument("--cognito-user-pool-id", default="", help="Cognito UserPool ID (for JWT mode)")
    parser.add_argument("--cognito-client-id", default="", help="Cognito M2M App Client ID (for JWT mode)")
    parser.add_argument("--scope", default="", help="OAuth scope (for client_credentials mode)")
    parser.add_argument("--user-client-id", default="", help="Cognito User Client ID (for USER_PASSWORD_AUTH mode)")
    parser.add_argument("--username", default="", help="Cognito username (for USER_PASSWORD_AUTH mode)")
    parser.add_argument("--password", default="", help="Cognito password (for USER_PASSWORD_AUTH mode)")
    parser.add_argument("--all-tools", action="store_true", help="Call every tool (not just hello_world)")
    args = parser.parse_args()

    if args.jwt:
        encoded_arn = urllib.parse.quote(args.runtime_arn, safe="")
        endpoint_url = f"https://bedrock-agentcore.{args.region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier={args.qualifier}"
        if args.username and args.password:
            # USER_PASSWORD_AUTH mode
            user_client_id = args.user_client_id or args.cognito_client_id
            token = get_user_token(args.region, user_client_id, args.username, args.password)
            label = f"USER_PASSWORD_AUTH  user={args.username}"
            print(f"Using JWT Bearer token auth ({label})")
        else:
            # client_credentials mode
            cognito = boto3.client("cognito-idp", region_name=args.region)
            resp = cognito.describe_user_pool_client(UserPoolId=args.cognito_user_pool_id, ClientId=args.cognito_client_id)
            client_secret = resp["UserPoolClient"]["ClientSecret"]
            token = get_jwt_token(args.region, args.cognito_domain, args.cognito_client_id, client_secret, args.scope)
            label = "client_credentials (M2M)"
            print(f"Using JWT Bearer token auth ({label})")

        def invoke(session_id, payload):
            return invoke_jwt(endpoint_url, token, session_id, payload)
    else:
        # SigV4 SDK mode
        client = boto3.client("bedrock-agentcore", region_name=args.region)
        label = "SigV4"
        print(f"Using SigV4 auth via SDK")

        def invoke(session_id, payload):
            return invoke_sigv4(client, args.runtime_arn, args.qualifier, session_id, payload)

    session_id, tool_names = run_initialize(invoke, label)

    if args.all_tools:
        run_all_tools(invoke, session_id, tool_names)
    else:
        # Default: single hello_world call
        print("\n--- tools/call hello_world ---")
        qualified = next((n for n in tool_names if n == "hello_world" or n.endswith("___hello_world")), "hello_world")
        _, body = invoke(session_id, {
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": qualified, "arguments": {"name": "World"}},
        })
        data = parse_sse(body)
        content = data.get("result", {}).get("content", [])
        for item in content:
            print(f"  {item.get('text', item)}")

        print("\nAll tests passed.")


if __name__ == "__main__":
    main()
