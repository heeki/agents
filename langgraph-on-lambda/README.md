# LangGraph Agent on AWS Lambda

This repository contains a LangGraph agent deployed on AWS Lambda with API Gateway, providing both synchronous and streaming endpoints for agent interactions using Amazon Bedrock.

## Project Structure

```
agents/
└── langgraph-on-lambda/
    ├── src/
    │   ├── agent.mts                    # LangGraph agent implementation with streaming
    │   └── fn.mjs                       # Lambda handler with sync/streaming endpoints
    ├── iac/
    │   ├── template.yaml                # SAM template for API Gateway and Lambda function
    │   └── openapi.yaml                 # OpenAPI specification for API Gateway
    ├── etc/
    │   ├── environment.template         # Configuration file template
    │   ├── environment.sh               # Active configuration file, sourced by makefile
    │   ├── envvars.json                 # Environment variables for local testing
    │   ├── event.json                   # Sample Lambda event payload
    │   └── prompt.json                  # Sample request payload
    ├── tmp/                             # Temporary files and test outputs
    ├── makefile                         # Build, deploy, and test targets
    ├── package.json                     # Node.js dependencies
    └── README.md
```

## Prerequisites

- Node.js 22+
- AWS CLI configured with a profile that has access to Lambda, API Gateway, CloudFormation, S3, and Bedrock
- AWS SAM CLI installed
- TypeScript and tsx for local development

## Quick Start

1) Initialize environment

```bash
cd langgraph-on-lambda
npm install
cp etc/environment.template etc/environment.sh
# edit etc/environment.sh with your values
```

2) Deploy Lambda function and API Gateway

```bash
make lambda
# capture the API endpoint output and update O_API_ENDPOINT in etc/environment.sh
```

3) Test the deployment

```bash
# Test synchronous endpoint
make curl.post.sync

# Test streaming endpoint
make curl.post.stream

# Test Lambda function directly
make lambda.invoke.sync
```

## Application Endpoints

- POST `/langgraph` → Returns complete response as plain text (synchronous)
- POST `/langgraph-streaming` → Streams response tokens as plain text (streaming)

The Lambda function uses Node.js 22.x runtime with LangGraph for agent orchestration and Amazon Bedrock for model inference.

## Environment Variables

Edit `etc/environment.sh` (copied from the template). Key values used by the Makefile include:

- **AWS CLI**: `PROFILE`, `REGION`, `BUCKET`
- **Lambda Function**: `P_API_STAGE`, `P_FN_MEMORY`, `P_FN_TIMEOUT`, `LAMBDA_STACK`, `LAMBDA_TEMPLATE`, `LAMBDA_OUTPUT`, `LAMBDA_PARAMS`
- **Outputs**: `O_FN` (function name), `O_API_ENDPOINT` (API Gateway URL)
- **Testing**: `P_PROMPT` (for test requests)

## Local Development

Run the agent locally:

```bash
# Run agent directly with TypeScript
make local.agent

# Test with local invoke
make local.invoke
```

The local development uses SAM's local API Gateway and Lambda runtime simulation.

## Deployment Notes

- **Architecture**: The Lambda function uses Node.js 22.x runtime with x86_64 architecture
- **Memory**: Configurable via `P_FN_MEMORY` parameter (default: 128MB)
- **Timeout**: Configurable via `P_FN_TIMEOUT` parameter (default: 60 seconds)
- **Dependencies**: Managed through npm and bundled with the deployment package
- **Bedrock Access**: The function has permissions to invoke Claude and Nova models via Bedrock
- **Logging**: CloudWatch logs with 7-day retention, includes Lambda Insights and X-Ray tracing

## Make Targets

Common targets (respect values from `etc/environment.sh`):

- `make lambda` — package and deploy the Lambda function and API Gateway
- `make lambda.delete` — delete the Lambda stack
- `make local.agent` — run agent locally with tsx
- `make local.api` — run API locally with SAM
- `make local.api.build` — build and run API locally
- `make local.invoke` — invoke Lambda function locally
- `make lambda.invoke.sync` — invoke deployed Lambda function synchronously
- `make lambda.invoke.async` — invoke deployed Lambda function asynchronously
- `make curl.post.sync` — test synchronous endpoint via API Gateway
- `make curl.post.stream` — test streaming endpoint via API Gateway

## Architecture

The deployment uses:
- **API Gateway**: REST API with OpenAPI 3.0 specification
- **Lambda**: Node.js 22.x runtime with LangGraph agent orchestration
- **CloudWatch**: Logging and monitoring with Lambda Insights
- **X-Ray**: Distributed tracing for request flow analysis
- **Bedrock**: AI model inference with Claude Sonnet 4 or Nova Lite
- **LangGraph**: Agent orchestration and streaming capabilities

## Troubleshooting

- **Streaming warnings**: The "contentBlockIndex already exists" warnings are internal to the LangChain/Bedrock SDK and don't affect functionality
- **Memory issues**: Increase `P_FN_MEMORY` if the agent runs out of memory during processing
- **Timeout issues**: Increase `P_FN_TIMEOUT` for longer-running agent operations
- **Tool call noise**: The agent filters out background tool calls from output, showing only the final AI response
