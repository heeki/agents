import { createReactAgent } from "@langchain/langgraph/prebuilt";
import { BedrockRuntimeClient, ConversationRole, ConverseStreamCommand} from "@aws-sdk/client-bedrock-runtime";
import { ChatBedrockConverse } from "@langchain/aws";
import { AIMessage, HumanMessage, ToolMessage } from '@langchain/core/messages';

const region = process.env.AWS_REGION || "us-east-1";
const client = new BedrockRuntimeClient({ region: region });
const modelId = "us.anthropic.claude-sonnet-4-20250514-v1:0";

// agent setup
const agentTools = [];
const agentModel = new ChatBedrockConverse({
  model: process.env.MODEL_ID || modelId,
  region: process.env.AWS_REGION || region,
  maxTokens: 1000,
  temperature: 0.5,
});
const agent = createReactAgent({
  llm: agentModel,
  tools: agentTools,
});

// convert base64 to string
function parseBase64(message) {
  return JSON.parse(Buffer.from(message, "base64").toString("utf-8"));
}

// handle synchronous
async function handleSynchronous(prompt) {
  try {
    const response = await agent.invoke({ messages: [new HumanMessage(prompt)] });
    return response.content;
  } catch (error) {
    console.error(`ERROR: Can't invoke '${modelId}'. Reason: ${error.message}`);
    return `Error: ${error.message}`;
  }
}

// handle streaming
async function handleStreaming(responseStream, prompt) {
  try {
    for await (
      const [message, _metadata] of await agent.stream(
        { messages: [new HumanMessage(prompt)] },
        { configurable: { thread_id: "1"}, streamMode: "messages" }
      )
    ) {
      // write only ai message chunks to the stream
      if (message.getType?.() !== 'ai') {
        continue;
      }
      // skip tool call chunks
      if (message.tool_call_chunks?.length) {
        console.log(message.tool_call_chunks);
        continue;
      }
      const content = message.content;
      // write string content directly
      if (typeof content === 'string') {
        console.log(content);
        responseStream.write(content);
        continue;
      }
      // write array content parts
      if (Array.isArray(content)) {
        for (const part of content) {
          if (typeof part === 'string') {
            console.log(part);
            responseStream.write(part);
          } else if (part?.type === 'text') {
            console.log(String(part.text ?? ''));
            responseStream.write(String(part.text ?? ''));
          }
        }
      }
    }
    responseStream.end();
  } catch (error) {
    console.error(`ERROR: Can't invoke '${modelId}'. Reason: ${error.message}`);
    responseStream.write(`Error: ${error.message}`);
    responseStream.end();
  }
}

// lambda handler
export const handler = awslambda.streamifyResponse(
  async (event, responseStream, context) => {
    console.log(JSON.stringify(event));
    const httpResponseMetadata = {
      statusCode: 200,
      headers: {
        "content-type": "text/plain",
        "x-custom-header": "example-custom-header"
      }
    };
    responseStream.write(JSON.stringify(httpResponseMetadata));
    responseStream.write("\x00".repeat(8));

    const body = event.isBase64Encoded ? parseBase64(event.body) : JSON.parse(event.body);
    console.log(JSON.stringify(body));

    // get the prompt from the request body with fallback
    const prompt = body?.prompt || body?.text || body?.message || "Describe the purpose of a 'hello world' program in one paragraph";

    switch (event.path) {
      case "/langgraph":
        await handleSynchronous(prompt);
        break;
      case "/langgraph-streaming":
        await handleStreaming(responseStream, prompt);
        break;
    }
  }
)