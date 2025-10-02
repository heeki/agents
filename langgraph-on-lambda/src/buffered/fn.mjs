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
    console.log(JSON.stringify(response));

    // extract the message content from the response
    const aiMessage = response.messages.find(msg => msg instanceof AIMessage);
    console.log(JSON.stringify(aiMessage));
    if (aiMessage?.content) {
      return aiMessage.content;
    }

    // otherwise try to get content from the last message
    const lastMessage = response.messages[response.messages.length - 1];
    console.log(JSON.stringify(lastMessage));
    if (lastMessage?.content) {
      return lastMessage.content;
    }

    return {"message": "No response content found"};
  } catch (error) {
    console.error(`ERROR: Can't invoke '${modelId}'. Reason: ${error.message}`);
    return {"message": `Error: ${error.message}`};
  }
}

// standard lambda handler
export const handler = async (event, context) => {
  console.log(JSON.stringify(event));

  try {
    const body = event.isBase64Encoded ? parseBase64(event.body) : JSON.parse(event.body);
    console.log(JSON.stringify(body));

    // get the prompt from the request body with fallback
    const prompt = body?.prompt || body?.text || body?.message || "Describe the purpose of a 'hello world' program in one paragraph";
    const response =await handleSynchronous(prompt);

    return {
      statusCode: 200,
      headers: {
        "content-type": "text/plain",
        "x-custom-header": "example-custom-header"
      },
      body: JSON.stringify(response)
    };

  } catch (error) {
    console.error(`ERROR: ${error.message}`);
    return {
      statusCode: 500,
      body: JSON.stringify({
        message: `Error: ${error.message}`
      })
    };
  }
}
