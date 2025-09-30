# Strands Agent on AWS Lambda

This repository contains a simple Strands FastAPI service deployed on AWS Lambda with API Gateway, providing both synchronous and streaming endpoints for AI agent interactions.

## Project Structure

```
agents/
└── strands-on-lambda/
    ├── src/
    │   ├── server.py                    # FastAPI app with /strands and /strands-streaming endpoints
    │   └── run.sh                       # Lambda bootstrap script
    ├── iac/
    │   ├── layer.yaml                   # Lambda layer for dependencies
    │   ├── template.yaml                # Template for API Gateway and Lambda function resources
    │   ├── openapi.yaml                 # OpenAPI specification for API Gateway
    ├── etc/
    │   ├── environment.sh               # Active configuration file, sourced by makefile
    │   ├── environment.template         # Configuration file template
    │   ├── prompt.json                  # Sample request payload
    │   └── envvars.json                 # Environment variables for local testing
    ├── build/                           # SAM build artifacts
    ├── tmp/                             # Temporary files and test outputs
    ├── makefile                         # Build, deploy, and test targets
    ├── requirements.txt                 # Python dependencies
    ├── pyproject.toml                   # Python project configuration
    └── README.md
```

## Prerequisites

- Python 3.12+
- AWS CLI configured with a profile that has access to Lambda, API Gateway, CloudFormation, S3, and Bedrock
- AWS SAM CLI installed
- Docker (for building Lambda layers)

## Quick Start

1) Initialize environment

```bash
cd strands-on-lambda
uv pip install -r requirements.txt
cp etc/environment.template etc/environment.sh
# edit etc/environment.sh with your values
```

2) Deploy Lambda layer (dependencies)

```bash
make layer
# capture the layer ARN output and update O_LAYER_ARN in etc/environment.sh
```

3) Deploy Lambda function and API Gateway

```bash
make lambda
# capture the API endpoint output and update O_API_ENDPOINT in etc/environment.sh
```

4) Test the deployment

```bash
# Test synchronous endpoint
make curl.post.sync

# Test streaming endpoint
make curl.post.stream

# Test Lambda function directly
make lambda.invoke.sync
```

## Application Endpoints

- POST `/strands` → Returns complete response as plain text (synchronous)
- POST `/strands-streaming` → Streams response tokens as plain text (streaming)

The Lambda function uses FastAPI with Lambda Adapter to handle HTTP requests through API Gateway. The app binds to port 8000 internally and uses the Lambda Adapter layer for request/response handling.

## Environment Variables

Edit `etc/environment.sh` (copied from the template). Key values used by the Makefile include:

- **AWS CLI**: `PROFILE`, `REGION`, `BUCKET`
- **Lambda Layer**: `P_DESCRIPTION`, `LAYER_STACK`, `LAYER_TEMPLATE`, `LAYER_OUTPUT`, `LAYER_PARAMS`, `O_LAYER_ARN`
- **Lambda Function**: `P_API_STAGE`, `P_FN_MEMORY`, `P_FN_TIMEOUT`, `LAMBDA_STACK`, `LAMBDA_TEMPLATE`, `LAMBDA_OUTPUT`, `LAMBDA_PARAMS`
- **Outputs**: `O_FN` (function name), `O_API_ENDPOINT` (API Gateway URL)
- **Testing**: `P_PROMPT` (for test requests)

## Local Development

Run the API locally using SAM:

```bash
# Build and run locally
make sam.local.api.build

# Or run without building
make sam.local.api

# Test with local invoke
make sam.local.invoke
```

The local development uses SAM's local API Gateway and Lambda runtime simulation.

## Deployment Notes

- **Architecture**: The Lambda function uses Python 3.13 runtime with x86_64 architecture
- **Memory**: Configurable via `P_FN_MEMORY` parameter (default: 128MB)
- **Timeout**: Configurable via `P_FN_TIMEOUT` parameter (default: 60 seconds)
- **Dependencies**: Managed through a separate Lambda layer for faster deployments
- **Bedrock Access**: The function has permissions to invoke Claude Sonnet 4 models via Bedrock
- **Logging**: CloudWatch logs with 7-day retention, includes Lambda Insights and X-Ray tracing

## Make Targets

Common targets (respect values from `etc/environment.sh`):

- `make layer` — build, package, and deploy the Lambda layer
- `make lambda` — package and deploy the Lambda function and API Gateway
- `make lambda.delete` — delete the Lambda stack
- `make sam.local.api` — run API locally with SAM
- `make sam.local.api.build` — build and run API locally
- `make sam.local.invoke` — invoke Lambda function locally
- `make lambda.invoke.sync` — invoke deployed Lambda function synchronously
- `make lambda.invoke.async` — invoke deployed Lambda function asynchronously
- `make curl.post.sync` — test synchronous endpoint via API Gateway
- `make curl.post.stream` — test streaming endpoint via API Gateway

## Architecture

The deployment uses:
- **API Gateway**: REST API with OpenAPI 3.0 specification
- **Lambda**: Python 3.13 runtime with FastAPI and Lambda Adapter
- **Lambda Layer**: Contains Python dependencies for faster deployments
- **CloudWatch**: Logging and monitoring with Lambda Insights
- **X-Ray**: Distributed tracing for request flow analysis
- **Bedrock**: AI model inference with Claude Sonnet 4
