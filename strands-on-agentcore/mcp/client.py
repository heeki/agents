import asyncio
import os
import sys
import httpx

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def main():
    agent_arn = os.getenv('AGENT_ARN')
    bearer_token = os.getenv('BEARER_TOKEN')
    if not agent_arn or not bearer_token:
        print("Error: AGENT_ARN or BEARER_TOKEN environment variable is not set")
        sys.exit(1)

    encoded_arn = agent_arn.replace(':', '%3A').replace('/', '%2F')
    mcp_url = f"https://bedrock-agentcore.us-east-1.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
    headers = {"authorization": f"Bearer {bearer_token}","content-type":"application/json"}
    print(f"Invoking: {mcp_url} \nwith headers: {headers}\n")

    try:
        async with streamablehttp_client(mcp_url, headers, timeout=120, terminate_on_close=False) as (
            read_stream,
            write_stream,
            _,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tool_result = await session.list_tools()
                for tool in tool_result.tools:
                    print(f"🔧 {tool.name}")
                    print(f"   Description: {tool.description}")
                    if hasattr(tool, 'inputSchema') and tool.inputSchema:
                        properties = tool.inputSchema.get('properties', {})
                        if properties:
                            print(f"   Parameters: {list(properties.keys())}")
                    print()
                print(f"✅ Successfully connected to MCP server!")
                print(f"Found {len(tool_result.tools)} tools available.")
    except ExceptionGroup as eg:
        for exc in eg.exceptions:
            if isinstance(exc, httpx.HTTPStatusError):
                print(f"❌ HTTP Error: {exc.response.status_code} {exc.response.reason_phrase}")
                print(f"   URL: {exc.request.url}")
                try:
                    response_text = exc.response.text
                    print(f"   Response: {response_text}")
                except httpx.ResponseNotRead:
                    print(f"   Response: [streaming response content not available]")
            else:
                print(f"❌ Error connecting to MCP server: {exc}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error connecting to MCP server: {e}")
        sys.exit(1)

asyncio.run(main())