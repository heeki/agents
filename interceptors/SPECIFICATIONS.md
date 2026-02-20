# Interceptors Prototype: Specification

## Objective

Build a prototype demonstrating Lambda-based request interceptors on AgentCore Gateway. The interceptor adds a custom HTTP header to MCP `tools/call` requests only, and the downstream MCP server logs the received header and full event payload to prove the transformation worked.

## Architecture

```
MCP Client
    |
    |--- Direct path ---> AgentCore Runtime (MCP Server)
    |
    |--- Gateway path --> AgentCore Gateway
                              |
                              +--> Request Interceptor (Lambda)
                              |        On tools/call: adds header
                              |        X-Amzn-Bedrock-AgentCore-Runtime-Custom-Interceptor-Demo
                              |        On other methods: passes through unchanged
                              |
                              +--> AgentCore Runtime (MCP Server)
                                       Logs custom header + full payload
```

## Projects

### Sub-Project 1: Lambda Interceptor (`interceptor/` + `iac/`)

Self-contained Lambda function and SAM infrastructure for the request interceptor.

### Sub-Project 2: AgentCore Resources (`agentcore/` + `app/`)

AgentCore Runtime (MCP server), Gateway, and target configuration managed primarily via the AgentCore CLI.

---

## Components

### 1. Request Interceptor (Python Lambda) — Sub-Project 1

- **Runtime**: Python 3.12
- **Handler**: `fn/handler.lambda_handler`
- **Behavior**:
  - Receives the interceptor input event (`interceptorInputVersion: "1.0"`)
  - Logs the full input event for schema visibility
  - Checks the MCP method in `gatewayRequest.body.method`
  - If method is `tools/call`:
    - Adds header `X-Amzn-Bedrock-AgentCore-Runtime-Custom-Interceptor-Demo` with value `intercepted-at-<ISO-timestamp>` to `transformedGatewayRequest.headers`
  - If method is anything else (e.g., `tools/list`, `initialize`):
    - Passes through with no header additions
  - Always passes the original request body through unchanged in `transformedGatewayRequest.body`
- **Deployment**: SAM template (`iac/interceptor.yaml`)
- **IAM**: SAM template also creates the AgentCore Gateway service role with:
  - Trust policy for `bedrock-agentcore.amazonaws.com`
  - `lambda:InvokeFunction` permission scoped to the interceptor function ARN
- **Test**: Local test invoke via `sam local invoke` with a sample event

### 2. MCP Server (Python, deployed to AgentCore Runtime) — Sub-Project 2

- **Framework**: `mcp.server.fastmcp.FastMCP` with `streamable-http` transport
- **Protocol**: MCP
- **Tool**: `hello_world` — accepts a `name: str` parameter and returns a greeting
- **Logging**: On every tool invocation, logs:
  - The full incoming HTTP request headers (to show the custom header when present)
  - The full event payload
- **Header access**: Via `RequestContext.request_headers` (AgentCore Runtime injects allowed headers)
- **Build**: CodeZip (managed by AgentCore CLI via `agentcore.json`)
- **Auth**: None (prototype only)
- **Network**: PUBLIC
- **Header allowlist**: Configure `request_header_allowlist` to include `X-Amzn-Bedrock-AgentCore-Runtime-Custom-Interceptor-Demo` via `agentcore configure --request-header-allowlist` or `.bedrock_agentcore.yaml`

### 3. AgentCore Gateway — Sub-Project 2

- **Protocol**: MCP
- **Auth**: NONE (prototype only)
- **Deployment**: `agentcore create_mcp_gateway` CLI command (not via `mcp.json`/`agentcore deploy`)
- **Phase 2 (no interceptor)**:
  ```bash
  agentcore create_mcp_gateway \
    --region us-east-1 \
    --name interceptors-demo-gateway \
    --role-arn <gateway-service-role-arn>
  ```
- **Phase 3 (with interceptor)**: Recreate the gateway with interceptor configuration:
  ```bash
  agentcore create_mcp_gateway \
    --region us-east-1 \
    --name interceptors-demo-gateway \
    --role-arn <gateway-service-role-arn> \
    --interceptor-configurations '[{
      "interceptor": {
        "lambda": {
          "arn": "<interceptor-lambda-arn>"
        }
      },
      "interceptionPoints": ["REQUEST"],
      "inputConfiguration": {
        "passRequestHeaders": true
      }
    }]'
  ```
- **Target**: Added via `agentcore add target` (preferred) or boto3 `create_gateway_target` (fallback)
  - Target type: `mcpServer` pointing to the AgentCore Runtime endpoint
  - No authorization configuration

### 4. MCP Test Client — Sub-Project 2

- **Purpose**: Validates end-to-end flow
- **Tests**:
  1. **Local**: `agentcore dev --logs` then test with MCP client
  2. **Direct to Runtime**: `agentcore invoke` to test the deployed MCP server
  3. **Through Gateway**: Python MCP client connecting to the Gateway MCP endpoint, calling `list_tools` and `hello_world`
- **Library**: `mcp.client.streamable_http.streamablehttp_client` + `mcp.ClientSession` (for Gateway path)
- **Verification**: After Gateway test, check CloudWatch logs for the interceptor Lambda and MCP server Runtime

---

## Event Schemas

### Interceptor Lambda Input (REQUEST)

Headers are included because `passRequestHeaders: true` is configured.

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
        "Mcp-Session-Id": "<session_id>",
        "User-Agent": "<client_user_agent>"
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

### Interceptor Lambda Output — tools/call (adds header)

```json
{
  "interceptorOutputVersion": "1.0",
  "mcp": {
    "transformedGatewayRequest": {
      "headers": {
        "X-Amzn-Bedrock-AgentCore-Runtime-Custom-Interceptor-Demo": "intercepted-at-2026-02-20T12:00:00Z"
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

### Interceptor Lambda Output — non-tools/call (passthrough)

```json
{
  "interceptorOutputVersion": "1.0",
  "mcp": {
    "transformedGatewayRequest": {
      "body": {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list"
      }
    }
  }
}
```

---

## Directory Structure

```
interceptors/
  CLAUDE.md
  SPECIFICATIONS.md
  README.md                           # Deployed configurations and test results
  makefile
  etc/
    environment.sh                    # Configurable parameters
  interceptor/                        # Sub-project 1: Lambda interceptor
    fn/
      handler.py                      # Lambda interceptor function
    events/
      test_event.json                 # Sample interceptor input event for testing
    iac/
      interceptor.yaml                # SAM template (Lambda + Gateway service role)
  agentcore/                          # Sub-project 2: AgentCore resources (managed by CLI)
    agentcore.json                    # Project spec (MCP server agent definition)
    aws-targets.json                  # Deployment targets (account, region)
    .bedrock_agentcore.yaml           # Runtime config (header allowlist)
    .env.local                        # Local env vars
    cdk/                              # CDK infrastructure (auto-generated by CLI)
  app/
    mcpserver/                        # MCP server code (referenced by agentcore.json)
      main.py                         # FastMCP hello_world server
      pyproject.toml                  # Python dependencies
  client/
    test_client.py                    # MCP test client for Gateway path
    requirements.txt                  # Client dependencies
```

---

## Deployment Workflow

### Sub-Project 1, Phase 1: Interceptor Lambda (SAM)

```bash
# Build and deploy the interceptor Lambda + Gateway service role
make interceptor.build               # sam build
make interceptor.deploy              # sam deploy

# Test invoke with sample event
make interceptor.invoke              # sam local invoke with test_event.json
```

### Sub-Project 2, Phase 1: MCP Server on AgentCore Runtime

```bash
# Initialize agentcore project
agentcore create                     # Create agentcore/ config files

# Local development and testing
agentcore dev --logs                 # Start local MCP server
# Test list_tools and invoke hello_world locally

# Deploy to AgentCore Runtime
agentcore deploy --yes --verbose     # Deploy MCP server to Runtime
agentcore status                     # Get deployed resource IDs

# Test deployed MCP server
agentcore invoke "Say hello to World" --stream
```

### Sub-Project 2, Phase 2: Gateway + Target (no interceptor)

```bash
# Create the gateway (no interceptor yet)
agentcore create_mcp_gateway \
  --region us-east-1 \
  --name interceptors-demo-gateway \
  --role-arn <gateway-service-role-arn>

# Add MCP server as gateway target
agentcore add target                 # Try CLI first; fallback to boto3

# Test through gateway
make test.gateway                    # MCP client -> Gateway -> Runtime
```

### Sub-Project 2, Phase 3: Attach Interceptor to Gateway

```bash
# Delete existing gateway
make gateway.delete                  # Delete gateway without interceptor

# Recreate gateway with interceptor configuration
agentcore create_mcp_gateway \
  --region us-east-1 \
  --name interceptors-demo-gateway \
  --role-arn <gateway-service-role-arn> \
  --interceptor-configurations '[{
    "interceptor": {
      "lambda": {
        "arn": "<interceptor-lambda-arn>"
      }
    },
    "interceptionPoints": ["REQUEST"],
    "inputConfiguration": {
      "passRequestHeaders": true
    }
  }]'

# Re-add MCP server as gateway target
agentcore add target                 # or boto3 fallback

# Test through gateway with interceptor
make test.gateway                    # Verify custom header is injected on tools/call
make logs.interceptor                # View interceptor Lambda logs
```

---

## IAM Configuration

### Gateway Service Role (created by SAM template)

**Trust Policy**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "bedrock-agentcore.amazonaws.com"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "aws:SourceAccount": "<ACCOUNT_ID>"
        }
      }
    }
  ]
}
```

**Permissions Policy**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "lambda:InvokeFunction",
      "Resource": "arn:aws:lambda:us-east-1:<ACCOUNT_ID>:function:<INTERCEPTOR_FUNCTION_NAME>"
    }
  ]
}
```

---

## Configuration Parameters (etc/environment.sh)

| Parameter | Description |
|-----------|-------------|
| `PROFILE` | AWS CLI profile (default) |
| `REGION` | AWS region (us-east-1) |
| `ACCOUNTID` | AWS account ID |
| `P_INTERCEPTOR_FUNCTION_NAME` | Lambda interceptor function name |
| `P_STACK_INTERCEPTOR` | SAM stack name for interceptor |
| `O_GATEWAY_ID` | Deployed Gateway ID (set after gateway creation) |
| `O_GATEWAY_ENDPOINT` | Gateway MCP endpoint URL (set after gateway creation) |
| `O_INTERCEPTOR_ARN` | Lambda interceptor ARN (derived from stack outputs) |
| `O_GATEWAY_ROLE_ARN` | Gateway service role ARN (derived from stack outputs) |
| `O_RUNTIME_ENDPOINT` | AgentCore Runtime invocation URL (from `agentcore status`) |

---

## Header Propagation Rules

Custom headers forwarded to AgentCore Runtime **must** use the prefix `X-Amzn-Bedrock-AgentCore-Runtime-Custom-`. Headers not matching this prefix (or `Authorization`) are stripped by the Runtime.

Constraints:
- Max header value size: 4KB
- Max 20 custom headers per runtime
- Headers must be added to the Runtime's `request_header_allowlist` configuration

Configuration via AgentCore CLI:
```bash
agentcore configure --request-header-allowlist "X-Amzn-Bedrock-AgentCore-Runtime-Custom-Interceptor-Demo"
```

Or manually in `.bedrock_agentcore.yaml`:
```yaml
request_header_allowlist:
  - "X-Amzn-Bedrock-AgentCore-Runtime-Custom-Interceptor-Demo"
```

---

## MCP Server Tool Definition

```python
@mcp.tool()
def hello_world(name: str) -> dict:
    """Says hello to the given name. Used to demonstrate Gateway interceptors."""
    # Log headers from the current request context
    # Log the full request details
    return {"greeting": f"Hello, {name}!", "timestamp": "<current_time>"}
```

---

## Success Criteria

1. **Sub-Project 1, Phase 1**: Interceptor Lambda deploys and returns correct output when test-invoked with a `tools/call` event (header added) and a `tools/list` event (passthrough)
2. **Sub-Project 2, Phase 1**: `agentcore dev` runs the MCP server locally; `list_tools` returns `hello_world`; `tools/call` returns a greeting. Deployed version works the same via `agentcore invoke`
3. **Sub-Project 2, Phase 2**: Gateway is created; target is added; `list_tools` and `tools/call` work through the gateway endpoint
4. **Sub-Project 2, Phase 3**: After interceptor is attached, `tools/call` through the gateway shows the `X-Amzn-Bedrock-AgentCore-Runtime-Custom-Interceptor-Demo` header in MCP server CloudWatch logs. `tools/list` does NOT show the header (interceptor only adds it on `tools/call`). Direct `agentcore invoke` does NOT show the header.

---

## Open Questions

1. **Header access in MCP server**: Verify whether `FastMCP` tool handlers can access HTTP headers via `RequestContext.request_headers` inside AgentCore Runtime, or if middleware is needed.
2. **`agentcore add target` for gateway**: Verify whether `agentcore add target` supports adding targets to a gateway created via `create_mcp_gateway`. If not, use boto3 `create_gateway_target`.
3. **Gateway update vs recreate**: Verify whether `agentcore create_mcp_gateway` supports updating an existing gateway with interceptor config, or if delete + recreate is required for Phase 3.
4. **Gateway target `metadataConfiguration`**: Verify whether `allowedRequestHeaders` needs to be explicitly set on the gateway target, or if it is automatically configured.

---

## References

- [AgentCore CLI](https://github.com/aws/agentcore-cli) (v0.3.0-preview)
- [Using interceptors with Gateway](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-interceptors.html)
- [Types of interceptors](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-interceptors-types.html)
- [Interceptor configuration](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-interceptors-configuration.html)
- [Interceptor examples](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-interceptors-examples.html)
- [Interceptor permissions](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-interceptors-permissions.html)
- [Gateway service role permissions](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-prerequisites-permissions.html)
- [Header propagation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-headers.html)
- [Runtime header allowlist](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-header-allowlist.html)
- [AWS sample: header propagation notebook](https://github.com/awslabs/amazon-bedrock-agentcore-samples/blob/main/01-tutorials/02-AgentCore-gateway/08-custom-header-propagation/gateway-interceptor-header-propagation.ipynb)
