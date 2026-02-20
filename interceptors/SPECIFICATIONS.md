# Interceptors Prototype: Specification

## Objective

Build a prototype demonstrating Lambda-based request interceptors on AgentCore Gateway. The interceptor adds a custom HTTP header to MCP tool call requests, and the downstream MCP server logs the received header and full event payload to prove the transformation worked.

## Architecture

```
MCP Client
    |
    |--- Direct path ---> AgentCore Runtime (MCP Server)
    |
    |--- Gateway path --> AgentCore Gateway
                              |
                              +--> Request Interceptor (Lambda)
                              |        Adds custom header: X-Amzn-Bedrock-AgentCore-Runtime-Custom-Interceptor-Demo
                              |
                              +--> AgentCore Runtime (MCP Server)
                                       Logs custom header + full payload
```

## Components

### 1. MCP Server (Python, deployed to AgentCore Runtime)

- **Framework**: `mcp.server.fastmcp.FastMCP` with `streamable-http` transport
- **Protocol**: MCP
- **Tool**: `hello_world` - a simple tool that accepts a `name: str` parameter and returns a greeting
- **Logging**: On every tool invocation, logs:
  - The full incoming HTTP request headers (to show the custom header)
  - The full event payload (to display the complete schema)
- **Header access**: Uses `context.request_headers` from `BedrockAgentCoreApp` `RequestContext` to read HTTP headers
- **Build**: CodeZip (managed by AgentCore CLI)
- **Auth**: None (prototype only)
- **Network**: PUBLIC

### 2. AgentCore Gateway

- **Protocol**: MCP
- **Auth**: NONE (prototype only)
- **Target**: MCP server endpoint pointing to the AgentCore Runtime invocation URL
- **Target metadata**: `allowedRequestHeaders` includes `X-Amzn-Bedrock-AgentCore-Runtime-Custom-Interceptor-Demo`
- **Interceptor**: Lambda function configured as REQUEST interceptor with `passRequestHeaders: true`
- **Deployment**: boto3 script (the AgentCore CLI v0.3.0-preview does not yet have gateway commands; `agentcore.json` schema covers Runtime, Memory, and Identity only)

### 3. Request Interceptor (Python Lambda)

- **Runtime**: Python 3.12
- **Handler**: `handler.lambda_handler`
- **Behavior**:
  - Receives the interceptor input event (version `1.0`)
  - Logs the full input event for schema visibility
  - Adds a custom header `X-Amzn-Bedrock-AgentCore-Runtime-Custom-Interceptor-Demo` with a timestamp value to `transformedGatewayRequest.headers`
  - Passes the original request body through unchanged in `transformedGatewayRequest.body`
- **Deployment**: SAM template (Lambda + IAM role)

### 4. MCP Test Client

- **Purpose**: Validates end-to-end flow
- **Tests**:
  1. **Direct to Runtime**: `agentcore invoke` to test the deployed MCP server
  2. **Through Gateway**: Python MCP client connecting to the Gateway MCP endpoint, calling `list_tools` and `hello_world`
- **Library**: `mcp.client.streamable_http.streamablehttp_client` + `mcp.ClientSession` (for Gateway path)
- **Verification**: After Gateway test, check CloudWatch logs for the interceptor Lambda and MCP server Runtime

## Tooling: AgentCore CLI (v0.3.0-preview)

The [AgentCore CLI](https://github.com/aws/agentcore-cli) is used as the primary interface for Runtime operations:

| Operation | Command |
|-----------|---------|
| Scaffold project | `agentcore create --name interceptors --defaults` |
| Add MCP agent (BYO) | `agentcore add agent --name mcpserver --type byo --language Python --code-location app/mcpserver/ --entrypoint main.py` |
| Local development | `agentcore dev --agent mcpserver --logs` |
| Local invocation | `agentcore dev --invoke "test prompt" --agent mcpserver --stream` |
| Package artifacts | `agentcore package --agent mcpserver` |
| Deploy to Runtime | `agentcore deploy --target default --yes` |
| Check status | `agentcore status --agent mcpserver` |
| Invoke deployed | `agentcore invoke "Hello World" --agent mcpserver --stream` |
| Validate config | `agentcore validate` |

**Note**: The CLI manages `agentcore/agentcore.json` (project spec), `agentcore/aws-targets.json` (deployment targets), and uses CDK under the hood for CloudFormation deployment. It handles CodeZip packaging, IAM role creation, and Runtime resource provisioning automatically.

**Not covered by CLI** (requires separate tooling):
- Lambda interceptor deployment (SAM)
- Gateway creation, target configuration, interceptor attachment (boto3 script)

## Directory Structure

```
interceptors/
  CLAUDE.md
  SPECIFICATIONS.md
  makefile
  etc/
    environment.sh                # Configurable parameters (Gateway, Lambda, etc.)
  agentcore/                      # Managed by AgentCore CLI
    agentcore.json                # Project spec (agents, memories, credentials)
    aws-targets.json              # Deployment targets (account, region)
    .env.local                    # Local env vars
    cdk/                          # CDK infrastructure (auto-generated)
  app/
    mcpserver/                    # MCP server agent code
      main.py                     # FastMCP hello_world server
      pyproject.toml              # Python dependencies
  interceptor/
    handler.py                    # Lambda interceptor function
  iac/
    interceptor.yaml              # SAM template for Lambda interceptor
    deploy_gateway.py             # boto3 script for Gateway + target + interceptor
  client/
    test_client.py                # MCP test client for Gateway path
    requirements.txt              # Client dependencies
```

## Event Schemas

### Interceptor Lambda Input (REQUEST)

```json
{
  "interceptorInputVersion": "1.0",
  "mcp": {
    "rawGatewayRequest": {
      "body": "<raw_request_body>"
    },
    "gatewayRequest": {
      "path": "/mcp",
      "httpMethod": "POST",
      "headers": {
        "Accept": "application/json",
        "Mcp-Session-Id": "<session_id>"
      },
      "body": {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
          "name": "hello_world",
          "arguments": {
            "name": "World"
          }
        }
      }
    }
  }
}
```

### Interceptor Lambda Output (REQUEST)

```json
{
  "interceptorOutputVersion": "1.0",
  "mcp": {
    "transformedGatewayRequest": {
      "headers": {
        "X-Amzn-Bedrock-AgentCore-Runtime-Custom-Interceptor-Demo": "intercepted-at-<timestamp>"
      },
      "body": {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
          "name": "hello_world",
          "arguments": {
            "name": "World"
          }
        }
      }
    }
  }
}
```

## Deployment Workflow

### Phase 1: MCP Server on AgentCore Runtime (AgentCore CLI)

```
1. agentcore create                # Scaffold project (or manually create agentcore.json)
2. agentcore add agent             # Add MCP server agent (BYO with custom code)
3. agentcore dev --agent mcpserver # Local dev/test
4. agentcore deploy --yes          # Deploy Runtime to AWS
5. agentcore invoke "hello"        # Verify deployed Runtime works
```

### Phase 2: Lambda Interceptor (SAM)

```
6. make interceptor                # sam deploy for Lambda function
```

### Phase 3: Gateway + Target + Interceptor (boto3)

```
7. make gateway.create             # Create Gateway (NONE auth)
8. make gateway.target             # Create target pointing to Runtime MCP endpoint
9. make gateway.interceptor        # Attach Lambda interceptor to Gateway
```

### Phase 4: End-to-End Testing

```
10. agentcore invoke "hello"            # Direct to Runtime (no custom header in logs)
11. make test.gateway                   # Through Gateway (custom header in logs)
12. make logs.interceptor               # View interceptor Lambda logs
13. make logs.runtime                   # View Runtime logs showing custom header
```

## Configuration Parameters (etc/environment.sh)

| Parameter | Description |
|-----------|-------------|
| `PROFILE` | AWS CLI profile |
| `REGION` | AWS region (us-east-1) |
| `ACCOUNTID` | AWS account ID |
| `P_GATEWAY_NAME` | Gateway name |
| `P_TARGET_NAME` | Gateway target name |
| `P_INTERCEPTOR_FUNCTION_NAME` | Lambda function name |
| `O_AGENT_ID` | Deployed Runtime agent ID (from `agentcore status`) |
| `O_AGENT_ARN` | Deployed Runtime agent ARN (from `agentcore status`) |
| `O_RUNTIME_ROLE_ARN` | Runtime execution role ARN (from `agentcore status`) |
| `O_GATEWAY_ID` | Deployed Gateway ID (output) |
| `O_GATEWAY_URL` | Gateway MCP endpoint URL (output) |
| `O_INTERCEPTOR_ARN` | Lambda interceptor ARN (output) |

**Note**: Runtime-specific parameters (agent name, build type, network mode) are managed in `agentcore/agentcore.json`, not in `environment.sh`.

## MCP Server Tool Definition

```python
@mcp.tool()
def hello_world(name: str) -> dict:
    """Says hello to the given name. Used to demonstrate Gateway interceptors."""
    # Log headers from the current request context
    # Log the full request details
    return {"greeting": f"Hello, {name}!", "timestamp": "<current_time>"}
```

## Success Criteria

1. `list_tools` returns the `hello_world` tool via both direct and gateway paths
2. `tools/call` for `hello_world` returns a greeting via both paths
3. CloudWatch logs for the interceptor Lambda show the full input event schema
4. CloudWatch logs for the MCP server Runtime show the `X-Amzn-Bedrock-AgentCore-Runtime-Custom-Interceptor-Demo` header when invoked via Gateway
5. CloudWatch logs for the MCP server Runtime do NOT show the `X-Amzn-Bedrock-AgentCore-Runtime-Custom-Interceptor-Demo` header when invoked directly (proving the interceptor is the source)

## Header Propagation Rules

Custom headers forwarded to AgentCore Runtime **must** use the prefix `X-Amzn-Bedrock-AgentCore-Runtime-Custom-`. Headers not matching this prefix (or `Authorization`) are stripped by the Runtime. Additional constraints:
- Max header value size: 4KB
- Max 20 custom headers per runtime
- Headers must be added to the Runtime's `request_header_allowlist` configuration

## Open Questions

1. **mcpServer target type**: Verify that the `mcpServer` target configuration is available in the current boto3 SDK version. If not, confirm alternative target configuration for pointing Gateway at an AgentCore Runtime endpoint.
2. **NONE authorizer**: Confirm that `authorizerType: NONE` is supported for Gateway creation (it was added in the Nov 2025 API update).
3. **Header access in MCP server**: The MCP server runs as a `FastMCP` process inside the AgentCore Runtime container. Verify whether `FastMCP` tool handlers can access `RequestContext.request_headers` (from `bedrock_agentcore`), or if the MCP server needs to be wrapped with `BedrockAgentCoreApp` to receive the headers.
4. **AgentCore CLI protocol configuration**: The CLI's `agentcore.json` schema does not include a `protocolConfiguration` field. Verify whether the CDK construct auto-detects MCP protocol from the server code, or if manual configuration is needed (e.g., overriding the CDK stack).

## References

- [AgentCore CLI](https://github.com/aws/agentcore-cli) (v0.3.0-preview)
- [Using interceptors with Gateway](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-interceptors.html)
- [Types of interceptors](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-interceptors-types.html)
- [Interceptor configuration](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-interceptors-configuration.html)
- [Interceptor examples](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-interceptors-examples.html)
- [Header propagation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-headers.html)
- [AWS sample: header propagation notebook](https://github.com/awslabs/amazon-bedrock-agentcore-samples/blob/main/01-tutorials/02-AgentCore-gateway/08-custom-header-propagation/gateway-interceptor-header-propagation.ipynb)
- [Runtime header allowlist](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-header-allowlist.html)
