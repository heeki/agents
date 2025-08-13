import json
import logging
import os
from bedrock_agentcore.memory import MemoryClient
from botocore.exceptions import ClientError
from strands.hooks import AgentInitializedEvent, HookProvider, HookRegistry, MessageAddedEvent
from lib.encoders import DateTimeEncoder

# agent constants
AGENT_NAME = os.getenv("AGENT_NAME", "test-agent")

# initialization
logging.getLogger(AGENT_NAME).setLevel(logging.INFO)

class AgentCoreMemory:
    def __init__(self, memory_client: MemoryClient):
        self.memory_client = memory_client

    def add_memory(self, memory_name: str, memory_description: str) -> str | None:
        try:
            # setting memory strategies to [] means that it will be short-term memory
            memory = self.memory_client.create_memory_and_wait(
                name=memory_name,
                description=memory_description,
                strategies=[],
                event_expiry_days=7
            )
            logging.info(f"✅ Memory created: {json.dumps(memory, cls=DateTimeEncoder)}")
            return memory['id']
        except ClientError as e:
            logging.error(f"❌ Error creating memory: {e}")
            if e.response['Error']['Code'] == 'ValidationException' and "already exists" in str(e):
                memories = self.memory_client.list_memories()
                logging.error(f"✅ Memories: {json.dumps(memories, cls=DateTimeEncoder)}")
                memory = next((m for m in memories if m['id'].startswith(memory_name)), None)
                logging.error(f"✅ Memory already exists: {json.dumps(memory, cls=DateTimeEncoder)}")
                return memory['id']
        except Exception as e:
            logging.error(f"❌ Unhandled error creating memory: {e}")
            raise e
        return None

class MemoryHookProvider(HookProvider):
    def __init__(self, memory_client: MemoryClient, memory_id: str, actor_id: str, session_id: str):
        self.memory_client = memory_client
        self.memory_id = memory_id
        self.actor_id = actor_id
        self.session_id = session_id

    def on_agent_initialized(self, event: AgentInitializedEvent):
        """Load recent conversation history when agent starts"""
        try:
            # Load the last 5 conversation turns from memory
            recent_turns = self.memory_client.get_last_k_turns(
                memory_id=self.memory_id,
                actor_id=self.actor_id,
                session_id=self.session_id,
                k=5
            )

            if recent_turns:
                # Format conversation history for context
                context_messages = []
                for turn in recent_turns:
                    for message in turn:
                        role = message['role']
                        content = message['content']['text']
                        context_messages.append(f"{role}: {content}")

                context = "\n".join(context_messages)
                # Add context to agent's system prompt.
                event.agent.system_prompt += f"\n\nRecent conversation:\n{context}"
                logging.info(f"✅ Loaded {len(recent_turns)} conversation turns")
        except Exception as e:
            logging.error(f"Memory load error: {e}")

    def on_message_added(self, event: MessageAddedEvent):
        """Store messages in memory"""
        messages = event.agent.messages
        try:
            self.memory_client.create_event(
                memory_id=self.memory_id,
                actor_id=self.actor_id,
                session_id=self.session_id,
                messages=[(str(messages[-1].get("content", "")), messages[-1]["role"])]
            )
        except Exception as e:
            logging.error(f"Memory save error: {e}")

    def register_hooks(self, registry: HookRegistry):
        # Register memory hooks
        registry.add_callback(MessageAddedEvent, self.on_message_added)
        registry.add_callback(AgentInitializedEvent, self.on_agent_initialized)
