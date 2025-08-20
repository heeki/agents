import logging
import os
from langchain.chat_models import init_chat_model
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from typing import Annotated
from typing_extensions import TypedDict

# initialization
name = os.getenv("AGENT_NAME", "test")
logging.getLogger(name).setLevel(logging.INFO)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s (%(name)s) [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)

# setup graph state
class State(TypedDict):
    # Messages have the type "list". The `add_messages` function
    # in the annotation defines how this state key should be updated
    # (in this case, it appends messages to the list, rather than overwriting them)
    messages: Annotated[list, add_messages]

# functions
def chatbot(state: State):
    return {"messages": [llm.invoke(state["messages"])]}

def stream_graph_updates(user_input: str):
    for event in graph.stream({"messages": [{"role": "user", "content": user_input}]}):
        for value in event.values():
            print("Assistant:", value["messages"][-1].content)

# define nodes
llm = init_chat_model(
    "anthropic.claude-3-sonnet-20240229-v1:0",
    model_provider="bedrock_converse",
)
# build graph
graph_builder = StateGraph(State)
graph_builder.add_node("chatbot", chatbot)
graph_builder.add_edge(START, "chatbot")
graph_builder.add_edge("chatbot", END)
graph = graph_builder.compile()

def main():
    while True:
        try:
            user_input = input("User: ")
            if user_input.lower() in ["quit", "exit", "q"]:
                print("Goodbye!")
                break
            stream_graph_updates(user_input)
        except:
            # fallback if input() is not available
            user_input = "What is VO2 max? What is the best way to improve it?"
            print("User: " + user_input)
            stream_graph_updates(user_input)
            break

if __name__ == "__main__":
    main()