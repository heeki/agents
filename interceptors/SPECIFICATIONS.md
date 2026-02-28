# Interceptors Prototype: Specification

## Objective

Build a prototype demonstrating Lambda-based request interceptors on AgentCore Gateway. The interceptor adds a custom HTTP header to MCP `tools/call` requests only, and the downstream MCP server logs the received header and full event payload to prove the transformation worked.

## Architecture

```
MCP Client
    |
    |--- Direct path ---> AgentCore Runtime (MCP Server)
    |                       Auth: JWT Bearer token (Cognito)
    |
    |--- Gateway path --> AgentCore Gateway
    |                       Auth: JWT Bearer token (Cognito)
                              |
                              +--> Request Interceptor (Lambda)
                              |        On tools/call: adds header
                              |        X-Amzn-Bedrock-AgentCore-Runtime-Custom-Interceptor-Demo
                              |        On other methods: passes through unchanged
                              |
                              +--> GatewayTarget (MCPServer type)
                              |        OAuth credential provider (Cognito client_credentials)
                              |
                              +--> AgentCore Runtime (MCP Server)
                                       Auth: CustomJWTAuthorizer (Cognito)
                                       Logs custom header + full payload
```

## Projects

### Sub-Project 1: Lambda Interceptor (`interceptor/`)

Self-contained Lambda function and SAM infrastructure for the request interceptor.

### Sub-Project 2: AgentCore Resources (`app/`, `gateway/`)

- **Phase 1**: MCP server on AgentCore Runtime (CloudFormation)
- **Phase 2**: AgentCore Gateway + GatewayTarget with OAuth (CloudFormation + API for credential provider resource)
- **Phase 3**: Attach Lambda interceptor to Gateway (CloudFormation `InterceptorConfigurations`)

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
- **Deployment**: SAM template (`interceptor/iac/interceptor.yaml`)
- **IAM**: SAM template also creates the AgentCore Gateway service role with:
  - Trust policy for `bedrock-agentcore.amazonaws.com`
  - `lambda:InvokeFunction` permission scoped to the interceptor function ARN
- **Test**: Local test invoke via `sam local invoke` with sample events

### 2. MCP Server (Python, deployed to AgentCore Runtime) — Sub-Project 2, Phase 1

- **Framework**: `mcp.server.fastmcp.FastMCP` with `streamable-http` transport
- **Protocol**: MCP (`stateless_http=True`)
- **Tool**: `hello_world` — accepts a `name: str` parameter, reads the custom interceptor header via `ctx.request_context.request.headers`, and returns the greeting + header value
- **ASGI middleware**: `HeaderEchoMiddleware` wraps the Starlette app to echo the interceptor request header back as a response header
- **Server startup**: Uses `mcp.streamable_http_app()` + middleware + `uvicorn.run()` instead of `mcp.run()`
- **Entry point**: `start.py` wraps `main.py` via `opentelemetry-instrument` auto-instrumentation (programmatic invocation, since EntryPoint doesn't support multi-command format)
- **OTEL**: `aws-opentelemetry-distro` provides the AWS OTEL distro, configurator, and instrumentors; runtime container env vars configure the auto-instrumentation. The AWS configurator registers `AwsCwOtlpBatchLogRecordProcessor` which writes logs directly to CloudWatch via botocore.
- **Logging**: On every tool invocation, logs request headers and interceptor header value
- **Build**: Zip package uploaded to S3 (md5-based naming)
- **Auth**: CustomJWTAuthorizer (Cognito OIDC discovery URL, AllowedClients)
- **Network**: PUBLIC
- **Header allowlist**: `X-Amzn-Bedrock-AgentCore-Runtime-Custom-Interceptor-Demo`
- **IaC**: CloudFormation template (`app/mcpserver/iac/runtime.yaml`)
- **Observability**: CloudWatch Logs delivery pipeline created via API (`app/mcpserver/setup_observability.py`)

### 3. AgentCore Gateway — Sub-Project 2, Phase 2

- **Protocol**: MCP (supportedVersions: `2025-03-26`, searchType: `SEMANTIC`)
- **Auth**: CUSTOM_JWT (Cognito — same user pool used for Runtime JWT auth)
- **Deployment**: CloudFormation template (`gateway/iac/gateway.yaml`) + API script (`gateway/setup_oauth.py`)
- **Resources managed by CFN** (`gateway/iac/gateway.yaml`):
  - Cognito UserPool, UserPoolDomain, ResourceServer, AppClient (for OAuth `client_credentials` flow)
  - Gateway IAM role (`bedrock-agentcore:*`, `agent-credential-provider:*`, `secretsmanager:GetSecretValue`, `lambda:InvokeFunction`)
  - Gateway (MCP protocol, AuthorizerType: CUSTOM_JWT, SearchType: SEMANTIC)
  - AuthorizerConfiguration: CustomJWTAuthorizer with Cognito OIDC discovery URL and AllowedClients
  - InterceptorConfigurations (conditional on `pInterceptorArn != NONE`):
    - InterceptionPoints: `REQUEST`
    - Interceptor: Lambda ARN from Sub-Project 1
    - InputConfiguration: `PassRequestHeaders: true`
  - GatewayTarget (conditional on `pCredentialProviderArn != NONE`):
    - MCPServer target pointing to AgentCore Runtime endpoint
    - Endpoint URL: `https://bedrock-agentcore.{REGION}.amazonaws.com/runtimes/{URL_ENCODED_ARN}/invocations?qualifier=DEFAULT`
    - `CredentialProviderConfigurations` referencing the OAuth2 credential provider ARN with scope
    - `MetadataConfiguration.AllowedRequestHeaders` — forwards the custom interceptor header from Gateway to Runtime
    - `MetadataConfiguration.AllowedResponseHeaders` — forwards custom response headers from Runtime back to client
- **Resource managed by API** (`gateway/setup_oauth.py`):
  - OAuth2 Credential Provider — no CFN resource type exists for this; created via `create_oauth2_credential_provider` API call
  - Stores the Cognito client ID and client secret for the `client_credentials` grant
  - Must be created before the GatewayTarget can reference it, and deleted before the Gateway stack is torn down

### 4. Authentication Flows

#### Client-to-Gateway Authentication (CUSTOM_JWT)

The Gateway uses CUSTOM_JWT authorization to authenticate inbound client requests using the same Cognito user pool:

1. **Gateway's `AuthorizerConfiguration`** (CFN) specifies a `CustomJWTAuthorizer` with the Cognito OIDC discovery URL and `AllowedClients`
2. Clients obtain a JWT token from Cognito using `client_credentials` flow (same token used for direct Runtime access)
3. Clients include the token as a `Bearer` token in the `Authorization` header
4. The Gateway validates the token before processing the request

#### Gateway-to-Runtime Authentication (OAuth2)

The Gateway-to-Runtime authentication uses Cognito OAuth2:

1. **Cognito UserPool** (CFN) provides the identity infrastructure
2. **CognitoResourceServer** (CFN) defines a custom scope (`invoke`)
3. **CognitoAppClient** (CFN) uses `client_credentials` grant with `GenerateSecret: true`
4. **OAuth2 Credential Provider** (API) stores the Cognito client ID and secret, configured with the Cognito OIDC discovery URL
5. **GatewayTarget** (CFN) references the credential provider ARN and scope in its `CredentialProviderConfigurations`
6. At request time, the Gateway's workload identity uses the credential provider to obtain a JWT token from Cognito
7. The Gateway forwards the request to the Runtime with the JWT token
8. **Runtime's CustomJWTAuthorizer** (CFN) validates the token via Cognito's OIDC discovery URL

**Key constraint**: SigV4 and JWT auth are mutually exclusive on a Runtime. When JWT auth is configured, the SDK's `invoke_agent_runtime` (which uses SigV4) no longer works. Direct invocation requires JWT Bearer tokens via HTTP.

**Key constraint**: Cognito access tokens from `client_credentials` grant do NOT include an `aud` claim. Neither the Runtime's nor the Gateway's `AllowedAudience` field should be set; use `AllowedClients` to validate the `client_id` claim instead.

**Key constraint**: The Gateway IAM role must include `agent-credential-provider:*` in addition to `bedrock-agentcore:*` for the OAuth token exchange to succeed at request time.

### 5. MCP Test Clients — Sub-Project 2

- **Runtime test** (`app/mcpserver/test_runtime.py`): Tests direct runtime invocation
  - SigV4 mode: uses boto3 SDK (when runtime has no JWT auth)
  - JWT mode: uses HTTP + Bearer token (when runtime has JWT auth)
- **Gateway test** (`gateway/test_gateway.py`): Tests end-to-end Gateway flow
  - Uses JWT Bearer token auth (Cognito `client_credentials` flow, same as Runtime test)
  - Obtains client secret via `describe_user_pool_client`, exchanges for JWT token at Cognito token endpoint
  - Tool names are qualified with target prefix (e.g., `interceptors-demo-mcpserver___hello_world`)

---

## Event Schemas

### Interceptor Lambda Input (REQUEST)

Headers are included because `InputConfiguration.PassRequestHeaders: true` is configured on the Gateway's `InterceptorConfigurations`.

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
  README.md
  makefile
  etc/
    environment.sh                    # Configurable parameters and stack outputs
  interceptor/                        # Sub-project 1: Lambda interceptor
    fn/
      handler.py                      # Lambda interceptor function
    events/
      test_tools_call.json            # Sample tools/call event
      test_tools_list.json            # Sample tools/list event
    iac/
      interceptor.yaml                # SAM template (Lambda + Gateway service role)
  app/
    mcpserver/                        # Sub-project 2, Phase 1: MCP server
      start.py                        # OTEL-instrumented entry point (wraps main.py)
      main.py                         # FastMCP hello_world server (reads interceptor headers)
      requirements.txt                # Python dependencies (mcp[cli], uvicorn, aws-opentelemetry-distro, boto3)
      test_runtime.py                 # Test script (SigV4 and JWT modes)
      setup_observability.py          # CloudWatch Logs delivery pipeline management (API)
      iac/
        runtime.yaml                  # CloudFormation template (Runtime + IAM role)
  gateway/                            # Sub-project 2, Phase 2: Gateway
    iac/
      gateway.yaml                    # CloudFormation template (Gateway + Cognito + Target)
    setup_oauth.py                    # OAuth2 credential provider management (API)
    test_gateway.py                   # Test script for Gateway MCP endpoint
```

---

## Deployment Workflow

### Sub-Project 1, Phase 1: Interceptor Lambda (SAM)

```bash
make interceptor.build
make interceptor.deploy
make interceptor.local.tools_call    # verify header injection
make interceptor.local.tools_list    # verify passthrough
```

### Sub-Project 2, Phase 1: MCP Server on AgentCore Runtime

```bash
make runtime.package                 # zip + upload to S3
make runtime.deploy                  # deploy CloudFormation stack
make runtime.status                  # verify runtime is READY
make runtime.invoke                  # test via JWT Bearer token
```

### Sub-Project 2, Phase 2: Gateway + Target (multi-step)

The Gateway deployment requires multiple steps because the GatewayTarget's `CredentialProviderConfigurations` references an OAuth2 Credential Provider ARN, but no CloudFormation resource type exists for credential providers. The provider must be created via API between CFN deploys.

```bash
# Step 1: Deploy Gateway + Cognito, no target (CFN)
# Set O_CREDENTIAL_PROVIDER_ARN=NONE in environment.sh for first deploy
make gateway.deploy
# Creates: Cognito UserPool/Domain/ResourceServer/AppClient, Gateway, IAM role
# GatewayTarget is skipped because pCredentialProviderArn=NONE
# Record outputs in environment.sh:
#   O_GATEWAY_ID, O_GATEWAY_URL, O_COGNITO_USER_POOL_ID,
#   O_COGNITO_CLIENT_ID, O_COGNITO_DISCOVERY_URL, O_COGNITO_ISSUER

# Step 2: Create OAuth2 credential provider (API)
make gateway.setup
# Reads Cognito client secret, calls create_oauth2_credential_provider API
# Record output in environment.sh: O_CREDENTIAL_PROVIDER_ARN

# Step 3: Update Runtime with JWT auth (CFN)
make runtime.deploy
# Adds CustomJWTAuthorizer referencing Cognito discovery URL and client ID

# Step 4: Verify Runtime accepts JWT tokens
make runtime.invoke

# Step 5: Redeploy Gateway with target (CFN)
# Set O_CREDENTIAL_PROVIDER_ARN to the real ARN in environment.sh
make gateway.deploy
# Creates GatewayTarget with CredentialProviderConfigurations referencing the provider

# Step 6: Test end-to-end through Gateway
make gateway.invoke
```

### Sub-Project 2, Phase 3: Attach Interceptor to Gateway

The interceptor is attached to the Gateway via the `InterceptorConfigurations` property in the same CFN template. Set `O_INTERCEPTOR_ARN` in `environment.sh` before deploying.

```bash
# Set O_INTERCEPTOR_ARN to the Lambda function ARN in environment.sh
make gateway.deploy                  # updates Gateway with InterceptorConfigurations
make gateway.invoke                  # test end-to-end (interceptor adds header on tools/call)
```

Verification via interceptor Lambda CloudWatch logs (`/aws/lambda/interceptors-demo-interceptor`):
- `initialize`: passthrough, no header added
- `tools/list`: passthrough, no header added
- `tools/call`: adds `X-Amzn-Bedrock-AgentCore-Runtime-Custom-Interceptor-Demo: intercepted-at-<ISO-timestamp>`

---

## IAM Configuration

### Gateway Service Role (Sub-Project 1)

Trust policy for `bedrock-agentcore.amazonaws.com` with `lambda:InvokeFunction` permission.

### Runtime Role (Sub-Project 2, Phase 1)

Trust policy for `bedrock-agentcore.amazonaws.com` with:
- `logs:DescribeLogGroups` on `Resource: "*"` (separate statement — cannot be scoped to a specific log group ARN)
- `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:DescribeLogStreams`, `logs:FilterLogEvents`, `logs:GetLogEvents`, `logs:PutLogEvents` scoped to `/aws/bedrock-agentcore/runtimes/*`
- `xray:PutTraceSegments`, `xray:PutTelemetryRecords` on `Resource: "*"` (required for OTEL trace export to X-Ray)

### Gateway Role (Sub-Project 2, Phase 2 + 3)

Trust policy for `bedrock-agentcore.amazonaws.com` with:
- `bedrock-agentcore:*` — broad AgentCore permissions (required for OAuth token exchange; scoped actions like `InvokeAgentRuntime` + `GetWorkloadAccessToken` + `GetResourceOauth2Token` are insufficient)
- `agent-credential-provider:*` — credential provider token exchange (required for Gateway to obtain OAuth tokens)
- `secretsmanager:GetSecretValue` — read credential provider secrets
- `lambda:InvokeFunction` — invoke the interceptor Lambda (Phase 3)

---

## Configuration Parameters (etc/environment.sh)

| Parameter | Description |
|-----------|-------------|
| `PROFILE` | AWS CLI profile |
| `REGION` | AWS region |
| `P_INTERCEPTOR_FUNCTION_NAME` | Lambda interceptor function name |
| `P_STACK_INTERCEPTOR` | SAM stack name for interceptor |
| `P_RUNTIME_NAME` | AgentCore Runtime name |
| `P_STACK_RUNTIME` | SAM stack name for runtime |
| `P_S3_BUCKET` | S3 bucket for runtime code artifacts |
| `P_GATEWAY_NAME` | AgentCore Gateway name |
| `P_STACK_GATEWAY` | SAM stack name for gateway |
| `P_COGNITO_DOMAIN` | Cognito UserPool domain prefix |
| `P_OAUTH_PROVIDER_NAME` | OAuth2 credential provider name |
| `O_*` | Stack outputs (ARNs, IDs, URLs) |

---

## Header Propagation Rules

Custom headers forwarded to AgentCore Runtime **must** use the prefix `X-Amzn-Bedrock-AgentCore-Runtime-Custom-`. Headers not matching this prefix (or `Authorization`) are stripped by the Runtime.

For end-to-end header propagation through the Gateway, three configurations are required:

1. **GatewayTarget `MetadataConfiguration.AllowedRequestHeaders`** — tells the Gateway to forward the header to the target (required even for interceptor-injected headers)
2. **Runtime `RequestHeaderAllowlist`** — tells the Runtime to pass the header to the application container
3. **MCP server code** — reads the header via `ctx.request_context.request.headers` (Starlette Request)

For response header propagation:
1. **MCP server code** — sets response headers via ASGI middleware wrapping `mcp.streamable_http_app()`
2. **GatewayTarget `MetadataConfiguration.AllowedResponseHeaders`** — tells the Gateway to forward the header back to the client

Constraints:
- Max header value size: 4KB
- Max 20 custom headers per runtime
- Headers must be added to the Runtime's `RequestHeaderAllowlist` in the CloudFormation template

## Observability

AgentCore Runtime does not emit application logs to CloudWatch by default. Two log groups exist per runtime:

### Vended Delivery Pipeline (API-managed)

Captures structured OTEL logs at the infrastructure level.

- **Script**: `app/mcpserver/setup_observability.py` — creates/deletes CloudWatch Logs delivery source, destination, and delivery
- **Log group**: `/aws/vendedlogs/bedrock-agentcore/runtime/APPLICATION_LOGS/<runtime-id>`
- **Log type**: Structured OTEL logs with request payloads, trace IDs, session IDs, span IDs, and request IDs
- **Scope**: MCP request/response payloads at the infrastructure level
- **Cleanup**: Must be deleted before deleting the runtime stack

```bash
make runtime.observability           # create delivery pipeline (one-time)
make runtime.logs                    # tail application logs
make runtime.observability.delete    # cleanup
```

### OTEL Application Log Group

The runtime infrastructure auto-creates a log group for application-level OTEL telemetry and runtime logs.

- **Log group**: `/aws/bedrock-agentcore/runtimes/<runtime-name>-<id>-DEFAULT`
- **Log streams**:
  - `otel-rt-logs` — structured OTEL log records with trace IDs, span IDs, and application log messages
  - `runtime-logs-<session-id>` — stdout/stderr from the application process

**OTEL container env vars** (set by runtime infrastructure):

| Env var | Value |
|---------|-------|
| `OTEL_PYTHON_DISTRO` | `aws_distro` |
| `OTEL_PYTHON_CONFIGURATOR` | `aws_configurator` |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | `http/protobuf` |
| `OTEL_EXPORTER_OTLP_TIMEOUT` | `5000` |
| `OTEL_EXPORTER_OTLP_LOGS_HEADERS` | `x-aws-log-group=...,x-aws-log-stream=otel-rt-logs,...` |
| `OTEL_TRACES_EXPORTER` | `otlp` |
| `OTEL_LOGS_EXPORTER` | `otlp` |
| `OTEL_TRACES_SAMPLER` | `parentbased_always_on` |
| `OTEL_PROPAGATORS` | `baggage,xray,tracecontext` |
| `OTEL_PYTHON_ID_GENERATOR` | `xray` |
| `OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED` | `true` |
| `OTEL_PYTHON_EXCLUDED_URLS` | `/ping` |
| `OTEL_PYTHON_DISABLED_INSTRUMENTATIONS` | `http,sqlalchemy,psycopg2,...,system_metrics,google-genai` |

**Runtime EnvironmentVariables** (set via CFN template):

| Env var | Value |
|---------|-------|
| `AGENT_OBSERVABILITY_ENABLED` | `true` |
| `AWS_REGION` | `!Ref pRegion` |

**Entry point and auto-instrumentation**:
- `start.py` wraps `main.py` via `opentelemetry.instrumentation.auto_instrumentation.run()`. Code configuration's EntryPoint only accepts single-script format (`["start.py"]`); multi-command format (`["opentelemetry-instrument", "python", "main.py"]`) fails `AWS::EarlyValidation::PropertyValidation`.
- The auto-instrumentation loads the AWS distro/configurator/instrumentors. `TracerProvider` is configured with `BatchSpanProcessor` + `BaggageSpanProcessor`. `LoggerProvider` is configured with the AWS-specific `AwsCwOtlpBatchLogRecordProcessor` that writes directly to CloudWatch via botocore (not via a localhost OTLP receiver).

**Prerequisites for OTEL to work**:
1. **`boto3`/`botocore` in deployment package** — the AWS OTEL distro's `OTLPAwsLogRecordExporter` uses botocore to write logs directly to CloudWatch. Without it, the entire AWS configurator fails: `ModuleNotFoundError: No module named 'botocore'`, `Configuration of aws_configurator failed`, `Failed to auto initialize OpenTelemetry`.
2. **`AWS_REGION` environment variable** — needed for the AWS configurator to auto-configure endpoints.
3. **IAM role with `logs:DescribeLogGroups` on `Resource: "*"`** — must be a separate statement (cannot be scoped to a specific log group ARN). Also needs `CreateLogStream`, `PutLogEvents`, `DescribeLogStreams`, `FilterLogEvents`, `GetLogEvents` scoped to the runtime log group.
4. **IAM role with `xray:PutTraceSegments` and `xray:PutTelemetryRecords` on `Resource: "*"`** — the OTEL trace exporter sends spans to X-Ray. Without these permissions, trace export fails with HTTP 403.

---

## Known Issues

1. **SigV4/JWT mutual exclusivity**: When the Runtime has CustomJWTAuthorizer configured, the boto3 SDK's `invoke_agent_runtime` (which uses SigV4) returns "Authorization method mismatch." Direct HTTP calls with JWT Bearer tokens must be used instead.

2. **Cognito aud claim**: Cognito access tokens from `client_credentials` grant do not include an `aud` claim. The runtime's `AllowedAudience` must not be set, or it will reject all tokens with "Claim 'aud' value mismatch."

3. **OAuth2 credential provider not in CFN**: No CloudFormation resource exists for `OAuth2CredentialProvider`. It must be managed via API calls (`gateway/setup_oauth.py`). Must be deleted before deleting the Gateway stack.

4. **Gateway role requires `agent-credential-provider:*`**: The Gateway role needs the `agent-credential-provider:*` IAM action namespace (in addition to `bedrock-agentcore:*`) for the OAuth token exchange to work when forwarding `tools/call` requests. Without it, `initialize` and `tools/list` succeed (served from cache) but `tools/call` fails with "An internal error occurred."

5. **Gateway `SearchType: SEMANTIC` requires no targets**: The `SearchType` property on the Gateway cannot be changed while targets exist. To modify, first deploy with `pCredentialProviderArn=NONE` to delete the target, then update the Gateway, then redeploy with the real ARN.

6. **OTEL auto-instrumentation requires botocore, AWS_REGION, and X-Ray permissions**: The AWS OTEL distro's `OTLPAwsLogRecordExporter` writes logs directly to CloudWatch via botocore API calls (not via a localhost OTLP receiver). If `botocore` is missing from the deployment package, the entire AWS configurator fails silently: `ModuleNotFoundError: No module named 'botocore'` → `Configuration of aws_configurator failed` → `Failed to auto initialize OpenTelemetry`. Additionally, `AWS_REGION` must be set as an environment variable. The IAM execution role must have `logs:DescribeLogGroups` on `Resource: "*"` as a separate statement, and `xray:PutTraceSegments` + `xray:PutTelemetryRecords` on `Resource: "*"` for trace export.

7. **GatewayTarget `AllowedRequestHeaders` required for interceptor headers**: Even though the interceptor adds a custom header to the request, the Gateway strips it before forwarding to the target unless the header is listed in `MetadataConfiguration.AllowedRequestHeaders` on the GatewayTarget.

8. **Gateway `AuthorizerType` is immutable**: The `AuthorizerType` property on a Gateway cannot be updated after creation. Attempting to change it (e.g., from `NONE` to `CUSTOM_JWT`) returns "Authorizer type cannot be updated for an existing gateway." To change, delete the entire Gateway stack and recreate it. This requires cascading updates: delete the OAuth credential provider first, delete the stack, redeploy with the new AuthorizerType, recreate the credential provider with new Cognito details, and update the Runtime with the new Cognito issuer.

---

## References

- [Using interceptors with Gateway](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-interceptors.html)
- [Interceptor configuration](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-interceptors-configuration.html)
- [Interceptor examples](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-interceptors-examples.html)
- [Header propagation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-headers.html)
- [Runtime header allowlist](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-header-allowlist.html)
- [Gateway target MCPServers](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-target-MCPservers.html)
- [CloudFormation: AWS::BedrockAgentCore::Gateway](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-bedrockagentcore-gateway.html)
- [CloudFormation: Gateway AuthorizerConfiguration](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-properties-bedrockagentcore-gateway-authorizerconfiguration.html)
- [CloudFormation: Gateway CustomJWTAuthorizerConfiguration](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-properties-bedrockagentcore-gateway-customjwtauthorizerconfiguration.html)
- [CloudFormation: Gateway InterceptorConfiguration](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-properties-bedrockagentcore-gateway-interceptorconfiguration.html)
- [CloudFormation: AWS::BedrockAgentCore::GatewayTarget](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-bedrockagentcore-gatewaytarget.html)
- [CloudFormation: AWS::BedrockAgentCore::Runtime](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-bedrockagentcore-runtime.html)
- [Runtime observability](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-configure.html)
