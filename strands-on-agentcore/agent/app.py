import boto3
import logging
import os
from strands import Agent
from strands.models import BedrockModel
from bedrock_agentcore import BedrockAgentCoreApp

name = os.getenv("AGENT_NAME", "test")
logging.getLogger(name).setLevel(logging.INFO)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s (%(name)s) [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
app = BedrockAgentCoreApp()
session = boto3.Session()
model = BedrockModel(
    # model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
    model_id="us.amazon.nova-lite-v1:0",
    max_tokens=1000,
    temperature=0.5,
    session=session
)
agent = Agent(
    model=model
)

@app.entrypoint
async def agent_invocation(payload, context):
    """Handler for agent invocation"""
    logging.info(f"Agent invocation payload: {payload}")
    logging.info(f"Agent invocation context: {context}")
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