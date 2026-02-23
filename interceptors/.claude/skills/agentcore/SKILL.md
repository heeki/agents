---
name: agentcore
description: Operational knowledge for Amazon Bedrock AgentCore — Runtime, Gateway, OTEL observability, OAuth, interceptors, and header propagation. Use when building or debugging AgentCore deployments.
user-invocable: true
disable-model-invocation: true
---

# Amazon Bedrock AgentCore — Operational Knowledge

Hard-won learnings from building MCP servers on AgentCore Runtime, routing through AgentCore Gateway with OAuth, attaching Lambda interceptors, and configuring OTEL observability.

---

## 1. CloudFormation Resource Types

### AWS::BedrockAgentCore::Runtime

Deploys an MCP server (or agent) as a managed container.

**Key properties:**
- `AgentRuntimeArtifact.CodeConfiguration.Runtime`: `PYTHON_3_12`
- `AgentRuntimeArtifact.CodeConfiguration.EntryPoint`: must be a single-element list (e.g., `["start.py"]`). Multi-command format like `["opentelemetry-instrument", "python", "main.py"]` fails `AWS::EarlyValidation::PropertyValidation`. Use a wrapper script instead.
- `ProtocolConfiguration`: `MCP` for MCP servers
- `NetworkConfiguration.NetworkMode`: `PUBLIC`
- `EnvironmentVariables`: key-value map injected into the container. The container also auto-sets OTEL env vars — only override if you need different values.
- `RequestHeaderConfiguration.RequestHeaderAllowlist`: headers the Runtime passes to the application. Must use prefix `X-Amzn-Bedrock-AgentCore-Runtime-Custom-`. Max 20 headers, 4KB per value.
- `AuthorizerConfiguration`: conditional JWT auth via `CustomJWTAuthorizer` with `DiscoveryUrl` and `AllowedClients`. Use `!If` + `AWS::NoValue` for conditional deployment.

**Deployment pattern:** Zip code + dependencies, upload to S3, reference via `S3.Bucket` + `S3.Prefix`. Use md5-based zip names for change detection.

### AWS::BedrockAgentCore::Gateway

Routes MCP clients to backend targets.

**Key properties:**
- `ProtocolType`: `MCP`
- `ProtocolConfiguration.Mcp.SupportedVersions`: `["2025-03-26"]`
- `ProtocolConfiguration.Mcp.SearchType`: `SEMANTIC` — WARNING: cannot change while targets exist. Delete targets first, update gateway, recreate targets.
- `AuthorizerType`: `NONE` for no client auth
- `InterceptorConfigurations`: conditional list via `!If`. Each entry has `InterceptionPoints` (`REQUEST`), `Interceptor.Lambda.Arn`, and `InputConfiguration.PassRequestHeaders`.

### AWS::BedrockAgentCore::GatewayTarget

Connects a Gateway to a backend (e.g., Runtime endpoint).

**Key properties:**
- `TargetConfiguration.Mcp.McpServer.Endpoint`: URL-encoded runtime ARN in the endpoint URL:
  ```
  https://bedrock-agentcore.{REGION}.amazonaws.com/runtimes/arn%3Aaws%3Abedrock-agentcore%3A{REGION}%3A{ACCOUNT}%3Aruntime%2F{RUNTIME_ID}/invocations?qualifier=DEFAULT
  ```
- `CredentialProviderConfigurations`: OAuth type referencing an OAuth2 Credential Provider ARN + scopes
- `MetadataConfiguration.AllowedRequestHeaders`: headers to forward from Gateway to target (required even for interceptor-injected headers — Gateway strips unlisted headers)
- `MetadataConfiguration.AllowedResponseHeaders`: headers to forward from target back to client

---

## 2. IAM Patterns

### Runtime Role

Trust policy for `bedrock-agentcore.amazonaws.com` with `SourceAccount` + `SourceArn` conditions.

Three IAM policy statements (this exact structure is required for OTEL to work):

```yaml
# Statement 1: DescribeLogGroups MUST be on Resource: "*"
# It is an account-level list operation — scoping to a log group ARN silently fails
- Effect: Allow
  Action:
    - logs:DescribeLogGroups
  Resource: "*"

# Statement 2: Log write actions scoped to runtime log group
- Effect: Allow
  Action:
    - logs:CreateLogGroup
    - logs:CreateLogStream
    - logs:DescribeLogStreams
    - logs:FilterLogEvents
    - logs:GetLogEvents
    - logs:PutLogEvents
  Resource: "arn:aws:logs:{REGION}:{ACCOUNT}:log-group:/aws/bedrock-agentcore/runtimes/*"

# Statement 3: X-Ray for OTEL trace export
- Effect: Allow
  Action:
    - xray:PutTraceSegments
    - xray:PutTelemetryRecords
  Resource: "*"
```

Without statement 1, the `OTLPAwsLogRecordExporter` silently fails to find/create the log group.
Without statement 3, trace export fails: `Failed to export span batch code: 403, reason: xray:PutTraceSegments`.

### Gateway Role

Requires broad permissions for the OAuth token exchange flow:

```yaml
- bedrock-agentcore:*           # AgentCore operations
- agent-credential-provider:*   # OAuth token exchange (CRITICAL — without this, tools/call fails while initialize/tools/list succeed from cache)
- secretsmanager:GetSecretValue  # Read credential provider secrets
- lambda:InvokeFunction          # Invoke interceptor Lambda
```

Scoped actions like `InvokeAgentRuntime` + `GetWorkloadAccessToken` + `GetResourceOauth2Token` are insufficient — use `bedrock-agentcore:*`.

---

## 3. OTEL Observability

### Architecture

The AWS OTEL distro does NOT use a localhost OTLP receiver. The `OTLPAwsLogRecordExporter` writes logs DIRECTLY to CloudWatch via botocore API calls. Traces are exported to X-Ray via the OTLP HTTP exporter.

### Entry Point Pattern

`start.py` wraps `main.py` via programmatic auto-instrumentation:

```python
import os, sys
script_dir = os.path.dirname(os.path.abspath(__file__))
main_py = os.path.join(script_dir, "main.py")
sys.argv = ["opentelemetry-instrument", sys.executable, main_py]
from opentelemetry.instrumentation.auto_instrumentation import run
run()
```

This is necessary because the Runtime's `EntryPoint` only accepts single-script format.

### Prerequisites (all required)

1. **`boto3`/`botocore` in deployment package** — hidden dependency. `aws-opentelemetry-distro` does not declare `botocore` as a hard dependency, but `OTLPAwsLogRecordExporter` imports `from botocore.session import Session`. Without it: `ModuleNotFoundError: No module named 'botocore'` -> `Configuration of aws_configurator failed` -> `Failed to auto initialize OpenTelemetry` -> zero telemetry exported.

2. **`AWS_REGION` environment variable** — set via `EnvironmentVariables` in CFN. Without it: `AWS region could not be determined. OTLP endpoints will not be automatically configured.`

3. **`AGENT_OBSERVABILITY_ENABLED=true`** — set via `EnvironmentVariables` in CFN. Enables the observability framework.

4. **IAM: `logs:DescribeLogGroups` on `Resource: "*"`** — separate statement, cannot be scoped. See IAM section above.

5. **IAM: `xray:PutTraceSegments` + `xray:PutTelemetryRecords`** — for trace export to X-Ray.

### Container Auto-Set Env Vars (do NOT override unless necessary)

| Env var | Value |
|---------|-------|
| `OTEL_PYTHON_DISTRO` | `aws_distro` |
| `OTEL_PYTHON_CONFIGURATOR` | `aws_configurator` |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | `http/protobuf` |
| `OTEL_EXPORTER_OTLP_TIMEOUT` | `5000` |
| `OTEL_EXPORTER_OTLP_LOGS_HEADERS` | routing headers (log group, stream) |
| `OTEL_TRACES_EXPORTER` | `otlp` |
| `OTEL_LOGS_EXPORTER` | `otlp` |
| `OTEL_TRACES_SAMPLER` | `parentbased_always_on` |
| `OTEL_PROPAGATORS` | `baggage,xray,tracecontext` |
| `OTEL_PYTHON_ID_GENERATOR` | `xray` |
| `OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED` | `true` |
| `OTEL_PYTHON_EXCLUDED_URLS` | `/ping` |

### Two Log Group Types

1. **Vended delivery pipeline** (`/aws/vendedlogs/bedrock-agentcore/runtime/APPLICATION_LOGS/<runtime-id>`):
   - Infrastructure-level structured OTEL logs (MCP request/response payloads, trace IDs, session IDs)
   - Created via API (`setup_observability.py`) — no CFN resource
   - Must be deleted before deleting the runtime stack

2. **OTEL application log group** (`/aws/bedrock-agentcore/runtimes/<runtime-name>-<id>-DEFAULT`):
   - `otel-rt-logs` stream: structured OTEL records with trace IDs, span IDs, application log messages
   - `runtime-logs-<session-id>` stream: stdout/stderr from application process (startup logs, uvicorn access logs)
   - Auto-created by runtime infrastructure

---

## 4. OAuth / JWT Authentication

### Flow

Gateway-to-Runtime auth uses Cognito `client_credentials` flow:

1. Cognito UserPool + Domain + ResourceServer + AppClient (all CFN)
2. OAuth2 Credential Provider stores client ID + secret (API call — no CFN resource type exists)
3. GatewayTarget references credential provider ARN + scope
4. At request time: Gateway obtains JWT from Cognito via credential provider -> forwards to Runtime
5. Runtime's `CustomJWTAuthorizer` validates token via Cognito OIDC discovery URL

### Pitfalls

- **No CFN resource for OAuth2 Credential Provider** — must manage via `create_oauth2_credential_provider` / `delete_oauth2_credential_provider` API calls. Must delete before tearing down Gateway stack.

- **Cognito `aud` claim**: Access tokens from `client_credentials` grant do NOT include an `aud` claim. Do NOT set `AllowedAudience` on the runtime's JWT authorizer — use `AllowedClients` (validates `client_id` claim) instead. Otherwise: "Claim 'aud' value mismatch."

- **SigV4/JWT mutual exclusivity**: When JWT auth is configured on a Runtime, the boto3 SDK's `invoke_agent_runtime` (SigV4) returns "Authorization method mismatch." Must use HTTP + JWT Bearer tokens for direct invocation.

### Multi-Step Deployment

The credential provider dependency forces this ordering:

```
Step 1: Deploy Gateway + Cognito (no target — credential provider ARN is empty)
Step 2: Create OAuth2 Credential Provider via API (needs Cognito client ID + secret)
Step 3: Update Runtime with JWT AuthorizerConfiguration (needs Cognito issuer URL)
Step 4: Redeploy Gateway with credential provider ARN (creates GatewayTarget)
```

Use conditional CFN resources (`!If` + `AWS::NoValue` or `Condition:`) to handle the phased deployment.

### Teardown Order

API-managed resources must be deleted before their CFN stacks:
```
1. Delete vended delivery pipeline (API)
2. Delete OAuth2 credential provider (API)
3. Delete Gateway stack (CFN)
4. Delete Runtime stack (CFN)
```

---

## 5. Header Propagation

### Required Prefix

Custom headers forwarded to AgentCore Runtime MUST use: `X-Amzn-Bedrock-AgentCore-Runtime-Custom-`

Headers without this prefix (except `Authorization`) are stripped by the Runtime.

### Three-Layer Configuration (request)

All three are required for a header to reach the MCP server tool handler:

1. **GatewayTarget `MetadataConfiguration.AllowedRequestHeaders`** — Gateway forwards header to target
2. **Runtime `RequestHeaderConfiguration.RequestHeaderAllowlist`** — Runtime passes header to container
3. **MCP server code** — reads via `ctx.request_context.request.headers` (Starlette Request)

Without layer 1, the Gateway strips the header even if the interceptor added it.

### Two-Layer Configuration (response)

1. **MCP server ASGI middleware** — sets response headers on `http.response.start` messages
2. **GatewayTarget `MetadataConfiguration.AllowedResponseHeaders`** — Gateway forwards back to client

---

## 6. Lambda Interceptors

### Input Schema (REQUEST)

```json
{
  "interceptorInputVersion": "1.0",
  "mcp": {
    "rawGatewayRequest": { "body": "<raw_request_body>" },
    "gatewayRequest": {
      "path": "/mcp",
      "httpMethod": "POST",
      "headers": { ... },
      "body": {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": { "name": "hello_world", "arguments": { "name": "World" } }
      }
    }
  }
}
```

Headers are only present when `InputConfiguration.PassRequestHeaders: true` is set on the Gateway's `InterceptorConfigurations`.

### Output Schema

```json
{
  "interceptorOutputVersion": "1.0",
  "mcp": {
    "transformedGatewayRequest": {
      "headers": { "X-Custom-Header": "value" },
      "body": { ... }
    }
  }
}
```

Omit `headers` in the output to pass through without adding headers.

### Pattern: Method-Conditional Header Injection

```python
mcp_method = event["mcp"]["gatewayRequest"]["body"].get("method", "unknown")
response = {
    "interceptorOutputVersion": "1.0",
    "mcp": {
        "transformedGatewayRequest": {
            "body": event["mcp"]["gatewayRequest"]["body"]
        }
    }
}
if mcp_method == "tools/call":
    response["mcp"]["transformedGatewayRequest"]["headers"] = {
        "X-Amzn-Bedrock-AgentCore-Runtime-Custom-MyHeader": "value"
    }
return response
```

---

## 7. MCP Server Patterns

### FastMCP with Streamable HTTP

```python
from mcp.server.fastmcp import FastMCP, Context
mcp = FastMCP("server-name", host="0.0.0.0", port=8000, stateless_http=True)

@mcp.tool()
def my_tool(name: str, ctx: Context) -> dict:
    header_val = ctx.request_context.request.headers.get("x-custom-header")
    return {"result": "...", "custom_header": header_val}

if __name__ == "__main__":
    app = mcp.streamable_http_app()
    app = MyMiddleware(app)  # optional ASGI middleware
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### ASGI Middleware for Response Headers

```python
class HeaderEchoMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        req_headers = dict(scope.get("headers", []))
        custom_val = req_headers.get(b"x-custom-header", b"")

        async def send_with_header(message):
            if message["type"] == "http.response.start" and custom_val:
                headers = list(message.get("headers", []))
                headers.append((b"x-custom-header", custom_val))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_header)
```

### Gateway Test Client (no auth)

When Gateway `AuthorizerType: NONE`, test with plain HTTP:
- `POST /mcp` with `{"jsonrpc": "2.0", "method": "initialize", ...}`
- Capture `mcp-session-id` from response headers for subsequent requests
- Tool names are target-prefixed: `{target-name}___{tool-name}`

---

## 8. Common Pitfalls Summary

| Issue | Symptom | Fix |
|-------|---------|-----|
| Missing `botocore` in deployment package | `ModuleNotFoundError: No module named 'botocore'`, zero OTEL telemetry | Add `boto3` to requirements.txt |
| Missing `AWS_REGION` env var | `AWS region could not be determined` | Set `AWS_REGION: !Ref pRegion` in EnvironmentVariables |
| `DescribeLogGroups` scoped to log group | OTEL log group not found/created, no `otel-rt-logs` stream | Separate statement with `Resource: "*"` |
| Missing X-Ray permissions | `Failed to export span batch code: 403` | Add `xray:PutTraceSegments` + `xray:PutTelemetryRecords` |
| Missing `agent-credential-provider:*` | `initialize`/`tools/list` work, `tools/call` fails | Add to Gateway role |
| Missing `AllowedRequestHeaders` on target | Interceptor adds header but Runtime never sees it | Add header to `MetadataConfiguration.AllowedRequestHeaders` |
| `AllowedAudience` set on JWT authorizer | All tokens rejected: "Claim 'aud' value mismatch" | Use `AllowedClients` instead (for Cognito `client_credentials`) |
| Changing `SearchType` with targets | CloudFormation update fails | Delete target first, update, recreate |
| Using `invoke_agent_runtime` with JWT auth | "Authorization method mismatch" | Use HTTP + Bearer token instead of SigV4 SDK |
| Multi-command `EntryPoint` | `AWS::EarlyValidation::PropertyValidation` failure | Use single wrapper script (e.g., `start.py`) |
