import { createReactAgent } from "@langchain/langgraph/prebuilt";
import { ChatBedrockConverse } from "@langchain/aws";
import { AIMessage, HumanMessage, ToolMessage } from '@langchain/core/messages';
import { TavilySearch } from "@langchain/tavily";

const agentTools = [new TavilySearch({ maxResults: 3 })];
const agentModel = new ChatBedrockConverse({
  model: process.env.MODEL_ID || 'us.anthropic.claude-sonnet-4-20250514-v1:0',
  region: process.env.AWS_REGION || 'us-east-1',
  maxTokens: 1000,
  temperature: 0.5,
});
const agent = createReactAgent({
  llm: agentModel,
  tools: agentTools,
});
const prompt = "What is VO2 max? What is the best way to improve it?";
// const prompt = "What does it mean if VO2 max appears to be decreasing over time?";

function writeMessageContent(content: unknown) {
  if (typeof content === 'string') {
    process.stdout.write(content);
    return;
  }
  if (!Array.isArray(content)) return;

  content.forEach(part => {
    if (typeof part === 'string') {
      process.stdout.write(part);
    } else if (part?.type === 'text') {
      process.stdout.write(String(part.text ?? ''));
    }
  });
}

// for streaming at the graph level
async function streamValues() {
  for await (
    const chunk of await agent.stream(
      { messages: [new HumanMessage(prompt)] },
      { configurable: { thread_id: "1"}, streamMode: "values" }
    )
  ) {
    const lastMessage = chunk.messages[chunk.messages.length - 1];
    if (lastMessage instanceof AIMessage) {
      console.log('[AIMessage]:', lastMessage.content);
    } else if (lastMessage instanceof HumanMessage) {
      console.log('[HumanMessage]:', lastMessage.content);
    } else if (lastMessage instanceof ToolMessage) {
      console.log('[ToolMessage]:', lastMessage.content);
    } else {
      console.log('[Other]:', lastMessage.constructor.name, lastMessage.content);
    }
  }
}

// for streaming at the message level
async function streamMessages() {
  for await (
    const [message, _metadata] of await agent.stream(
      { messages: [new HumanMessage(prompt)] },
      { configurable: { thread_id: "1"}, streamMode: "messages" }
    )
  ) {
    const m: any = message as any;
    if (m.getType?.() === 'ai') {
      if (m.tool_call_chunks?.length) {
        continue;
      }
      writeMessageContent(m.content);
    }
  }
}

// await streamValues();
await streamMessages();