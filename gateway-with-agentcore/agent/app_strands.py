import json
import logging
import os
from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient
from strands import Agent
from bedrock_agentcore import BedrockAgentCoreApp

name = os.getenv("AGENT_NAME", "template-strands")
gateway_url = os.getenv("GATEWAY_URL", "http://localhost:8080")
access_token = os.getenv("ACCESS_TOKEN", "invalid-access-token")
id_token = os.getenv("ID_TOKEN", "invalid-id-token")
logging.getLogger(name).setLevel(logging.INFO)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s (%(name)s) [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
app = BedrockAgentCoreApp()
headers = {"Authorization": f"Bearer {access_token}"}
logging.info(json.dumps({"gateway_url": gateway_url, "headers": headers}))

@app.entrypoint
async def agent_invocation(event, context):
    """Handler for agent invocation"""
    logging.info(f"Agent invocation event: {event}")
    logging.info(f"Agent invocation context: {context}")
    user_message = event.get(
        "prompt", "No prompt found in input, please guide customer to create a json event with prompt key"
    )
    streamable_http_mcp_client = MCPClient(lambda: streamablehttp_client(gateway_url, headers))
    with streamable_http_mcp_client:
        tools = streamable_http_mcp_client.list_tools_sync()
        agent = Agent(tools=tools)
        result = agent.stream_async(user_message)
        async for chunk in result:
            if 'data' in chunk:
                # Log chunk info for debugging without printing the actual data
                logging.info(f"{chunk['data']}  ({len(chunk['data'])} characters)")
                yield (chunk['data'])

if __name__ == "__main__":
    app.run()