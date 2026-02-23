import argparse
import base64
import boto3
import json
import sys
import urllib.parse

import requests


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Test MCP server on AgentCore Runtime")
    parser.add_argument("runtime_arn", help="AgentCore Runtime ARN")
    parser.add_argument("--qualifier", default="DEFAULT", help="Runtime endpoint qualifier")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument("--jwt", action="store_true", help="Use JWT Bearer token auth instead of SigV4")
    parser.add_argument("--cognito-domain", default="", help="Cognito UserPool domain prefix (for JWT mode)")
    parser.add_argument("--cognito-user-pool-id", default="", help="Cognito UserPool ID (for JWT mode)")
    parser.add_argument("--cognito-client-id", default="", help="Cognito App Client ID (for JWT mode)")
    parser.add_argument("--scope", default="", help="OAuth scope (for JWT mode)")
    args = parser.parse_args()

    if args.jwt:
        # JWT Bearer token mode
        cognito = boto3.client("cognito-idp", region_name=args.region)
        resp = cognito.describe_user_pool_client(UserPoolId=args.cognito_user_pool_id, ClientId=args.cognito_client_id)
        client_secret = resp["UserPoolClient"]["ClientSecret"]
        token = get_jwt_token(args.region, args.cognito_domain, args.cognito_client_id, client_secret, args.scope)
        encoded_arn = urllib.parse.quote(args.runtime_arn, safe="")
        endpoint_url = f"https://bedrock-agentcore.{args.region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier={args.qualifier}"
        print(f"Using JWT Bearer token auth")

        def invoke(session_id, payload):
            return invoke_jwt(endpoint_url, token, session_id, payload)
    else:
        # SigV4 SDK mode
        client = boto3.client("bedrock-agentcore", region_name=args.region)
        print(f"Using SigV4 auth via SDK")

        def invoke(session_id, payload):
            return invoke_sigv4(client, args.runtime_arn, args.qualifier, session_id, payload)

    # Initialize
    print("\n=== initialize ===")
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
    print(json.dumps(data, indent=2))

    # tools/list
    print("\n=== tools/list ===")
    _, body = invoke(session_id, {
        "jsonrpc": "2.0", "id": 2, "method": "tools/list",
    })
    data = parse_sse(body)
    tools = data.get("result", {}).get("tools", [])
    for tool in tools:
        print(f"  - {tool['name']}: {tool['description']}")

    # tools/call hello_world
    print("\n=== tools/call hello_world ===")
    _, body = invoke(session_id, {
        "jsonrpc": "2.0", "id": 3, "method": "tools/call",
        "params": {"name": "hello_world", "arguments": {"name": "World"}},
    })
    data = parse_sse(body)
    content = data.get("result", {}).get("content", [])
    for item in content:
        print(f"  {item.get('text', item)}")

    print("\nAll tests passed.")


if __name__ == "__main__":
    main()
