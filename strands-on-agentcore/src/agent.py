import logging
import os
from strands import Agent
from bedrock_agentcore import BedrockAgentCoreApp

name = os.getenv("AGENT_NAME", "test")
logging.getLogger(name).setLevel(logging.INFO)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s (%(name)s) [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
app = BedrockAgentCoreApp()
agent = Agent()

@app.entrypoint
async def agent_invocation(payload):
    """Handler for agent invocation"""
    user_message = payload.get(
        "prompt", "No prompt found in input, please guide customer to create a json payload with prompt key"
    )
    result = agent.stream_async(user_message)
    async for chunk in result:
        if 'data' in chunk:
            # Log chunk info for debugging without printing the actual data
            logging.info(f"{chunk['data']}  ({len(chunk['data'])} characters)")
            yield (chunk['data'])

if __name__ == "__main__":
    app.run()