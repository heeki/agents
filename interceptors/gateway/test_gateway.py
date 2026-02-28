import argparse
import base64
import json
import sys

import boto3
import requests


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


def send_rpc(url: str, rpc_id: int, method: str, token: str, params: dict | None = None, session_id: str | None = None) -> tuple[str, dict, dict]:
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
    r.raise_for_status()
    sid = r.headers.get("Mcp-Session-Id", session_id or "")
    resp_headers = dict(r.headers)
    body = r.text
    for line in body.strip().splitlines():
        if line.startswith("data: "):
            return sid, json.loads(line[6:]), resp_headers
    return sid, json.loads(body), resp_headers


def main() -> None:
    parser = argparse.ArgumentParser(description="Test MCP server through AgentCore Gateway")
    parser.add_argument("gateway_url", help="AgentCore Gateway MCP endpoint URL")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument("--cognito-domain", required=True, help="Cognito UserPool domain prefix")
    parser.add_argument("--cognito-user-pool-id", required=True, help="Cognito UserPool ID")
    parser.add_argument("--cognito-client-id", required=True, help="Cognito App Client ID")
    parser.add_argument("--scope", required=True, help="OAuth scope")
    args = parser.parse_args()

    # Get JWT token from Cognito
    cognito = boto3.client("cognito-idp", region_name=args.region)
    resp = cognito.describe_user_pool_client(UserPoolId=args.cognito_user_pool_id, ClientId=args.cognito_client_id)
    client_secret = resp["UserPoolClient"]["ClientSecret"]
    token = get_jwt_token(args.region, args.cognito_domain, args.cognito_client_id, client_secret, args.scope)
    print("Using JWT Bearer token auth")

    # Initialize
    print("\n=== initialize ===")
    session_id, data, resp_headers = send_rpc(args.gateway_url, 1, "initialize", token, {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "test-gateway-client", "version": "1.0"},
    })
    print(f"Session: {session_id}")
    print(json.dumps(data, indent=2))
    print("Response headers:")
    for k, v in resp_headers.items():
        print(f"  {k}: {v}")

    # tools/list
    print("\n=== tools/list ===")
    _, data, resp_headers = send_rpc(args.gateway_url, 2, "tools/list", token, session_id=session_id)
    tools = data.get("result", {}).get("tools", [])
    for tool in tools:
        print(f"  - {tool['name']}: {tool.get('description', '')}")
    print("Response headers:")
    for k, v in resp_headers.items():
        print(f"  {k}: {v}")

    # tools/call hello_world (find qualified name from tools/list)
    tool_name = next(
        (t["name"] for t in tools if "hello_world" in t["name"]),
        tools[0]["name"] if tools else "hello_world",
    )
    print(f"\n=== tools/call {tool_name} ===")
    _, data, resp_headers = send_rpc(args.gateway_url, 3, "tools/call", token, {
        "name": tool_name,
        "arguments": {"name": "World"},
    }, session_id=session_id)
    if "error" in data:
        print(f"  Error: {data['error'].get('message', data['error'])}")
        sys.exit(1)
    result = data.get("result", {})
    if result.get("isError"):
        print(f"  Server error: {result.get('content', [{}])[0].get('text', 'unknown')}")
        sys.exit(1)
    content = result.get("content", [])
    for item in content:
        print(f"  {item.get('text', item)}")
    print("Response headers:")
    for k, v in resp_headers.items():
        print(f"  {k}: {v}")

    print("\nAll tests passed.")


if __name__ == "__main__":
    main()
