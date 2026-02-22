import argparse
import boto3
import json
import sys


def invoke(client: boto3.client, runtime_arn: str, qualifier: str, session_id: str | None, payload: dict) -> tuple[str, str]:
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
    args = parser.parse_args()

    client = boto3.client("bedrock-agentcore", region_name=args.region)

    # Initialize
    print("=== initialize ===")
    session_id, body = invoke(client, args.runtime_arn, args.qualifier, None, {
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
    _, body = invoke(client, args.runtime_arn, args.qualifier, session_id, {
        "jsonrpc": "2.0", "id": 2, "method": "tools/list",
    })
    data = parse_sse(body)
    tools = data.get("result", {}).get("tools", [])
    for tool in tools:
        print(f"  - {tool['name']}: {tool['description']}")

    # tools/call hello_world
    print("\n=== tools/call hello_world ===")
    _, body = invoke(client, args.runtime_arn, args.qualifier, session_id, {
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
