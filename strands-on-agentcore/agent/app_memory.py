import logging
import os
from bedrock_agentcore import BedrockAgentCoreApp
from bedrock_agentcore.memory import MemoryClient
from strands import Agent
from providers.memory import AgentCoreMemory, MemoryHookProvider

# agent constants
AGENT_NAME = os.getenv("AGENT_NAME", "test-agent")
REGION = os.getenv("AWS_REGION", "us-east-1")
USER_ID = os.getenv("USER_ID", "test-user")
SESSION_ID = os.getenv("SESSION_ID", "0198a3d4-7ad4-7b3a-addb-0944840446be")

# memory constants
MEMORY_NAME = "test_short_term_memory"
MEMORY_DESCRIPTION = "short-term memory for the agent"
NO_PROMPT_FOUND_MESSAGE = "No prompt found in input, please guide customer to create a json payload with prompt key"

# memory initialization
memory_client = MemoryClient(region_name=REGION)
memory = AgentCoreMemory(memory_client)
memory_id = memory.add_memory(MEMORY_NAME, MEMORY_DESCRIPTION)
logging.info(f"✅ Memory ID: {memory_id}")

# initialization
logging.getLogger(AGENT_NAME).setLevel(logging.INFO)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s (%(name)s) [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
app = BedrockAgentCoreApp()
agent = Agent(
    name=AGENT_NAME,
    hooks=[MemoryHookProvider(memory_client, memory_id, USER_ID, SESSION_ID)]
)

@app.entrypoint
async def agent_invocation(payload, context):
    """Handler for agent invocation"""
    logging.info(f"Agent invocation payload: {payload}")
    logging.info(f"Agent invocation context: {context}")
    user_message = payload.get(
        "prompt", NO_PROMPT_FOUND_MESSAGE
    )
    result = agent.stream_async(user_message)
    async for chunk in result:
        if 'data' in chunk:
            # Log chunk info for debugging without printing the actual data
            logging.info(f"{chunk['data']}  ({len(chunk['data'])} characters)")
            yield (chunk['data'])

if __name__ == "__main__":
    app.run()