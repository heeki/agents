# Interceptors Prototype

Demonstrates Lambda-based request interceptors on AgentCore Gateway. The interceptor adds a custom HTTP header (`X-Amzn-Bedrock-AgentCore-Runtime-Custom-Interceptor-Demo`) to MCP `tools/call` requests, and the downstream MCP server logs the header to prove the transformation worked.

## Architecture

```
MCP Client
    |
    |--- Direct path ---> AgentCore Runtime (MCP Server)
    |                       Auth: JWT Bearer token (Cognito)
    |
    |--- Gateway path --> AgentCore Gateway (no client auth)
                              |
                              +--> Request Interceptor (Lambda)
                              |        On tools/call: adds header
                              |        On other methods: passes through unchanged
                              |
                              +--> GatewayTarget (MCPServer + OAuth)
                              |
                              +--> AgentCore Runtime (MCP Server)
                                       Auth: JWT (Cognito)
```

## Directory Structure

```
interceptors/
  makefile                            # Build, deploy, and test commands
  etc/
    environment.sh                    # Configurable parameters and stack outputs
  interceptor/                        # Sub-project 1: Lambda interceptor
    fn/
      handler.py                      # Lambda interceptor function
    events/
      test_tools_call.json            # Sample tools/call event (header injected)
      test_tools_list.json            # Sample tools/list event (passthrough)
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
        runtime.yaml                  # CFN template (AgentCore Runtime + IAM role + JWT auth)
  gateway/                            # Sub-project 2, Phase 2: Gateway
    iac/
      gateway.yaml                    # CFN template (Gateway + Cognito + Target)
    setup_oauth.py                    # OAuth2 credential provider management (API)
    test_gateway.py                   # Test script for Gateway MCP endpoint
```

## Sub-Project 1: Lambda Interceptor

Self-contained Lambda function that intercepts MCP requests on AgentCore Gateway. On `tools/call` requests, it adds a custom header with a timestamp. All other methods pass through unchanged.

### Resources

| Resource | Value |
|----------|-------|
| Stack name | `interceptors-demo-interceptor` |
| Lambda function | `interceptors-demo-interceptor` |
| Gateway service role | `interceptors-demo-interceptor-gateway-role` |
| IaC | SAM template (`interceptor/iac/interceptor.yaml`) |

### Commands

| Target | Description |
|--------|-------------|
| `interceptor.build` | SAM build the interceptor Lambda |
| `interceptor.deploy` | SAM deploy the interceptor stack |
| `interceptor.delete` | SAM delete the interceptor stack |
| `interceptor.local.tools_call` | Local test with `tools/call` event (header injected) |
| `interceptor.local.tools_list` | Local test with `tools/list` event (passthrough) |

### Workflow

```bash
make interceptor.build
make interceptor.deploy
make interceptor.local.tools_call    # verify header injection
make interceptor.local.tools_list    # verify passthrough
```

## Sub-Project 2, Phase 1: MCP Server on AgentCore Runtime

Stateless MCP server deployed to AgentCore Runtime via CloudFormation. Exposes a `hello_world` tool. Configured with JWT authentication via Cognito. Uses OTEL auto-instrumentation via `start.py` wrapping `main.py` with `aws-opentelemetry-distro`.

### Resources

| Resource | Value |
|----------|-------|
| Stack name | `interceptors-demo-runtime` |
| Runtime name | `interceptors_demo_mcpserver` |
| Protocol | MCP (stateless streamable-http) |
| Network | PUBLIC |
| Auth | CustomJWTAuthorizer (Cognito) |
| Header allowlist | `X-Amzn-Bedrock-AgentCore-Runtime-Custom-Interceptor-Demo` |
| IaC | CloudFormation template (`app/mcpserver/iac/runtime.yaml`) |

### Commands

| Target | Description |
|--------|-------------|
| `runtime.package` | Zip dependencies + code to `tmp/`, upload to S3 with md5-based name |
| `runtime.deploy` | SAM deploy the AgentCore Runtime stack (references S3 artifact) |
| `runtime.delete` | SAM delete the AgentCore Runtime stack |
| `runtime.invoke` | Test deployed runtime via JWT Bearer token (initialize, tools/list, tools/call) |
| `runtime.observability` | Create CloudWatch Logs delivery pipeline for runtime application logs |
| `runtime.observability.delete` | Delete CloudWatch Logs delivery pipeline |
| `runtime.observability.get` | Get delivery pipeline details |
| `runtime.logs` | Tail runtime application logs from CloudWatch |
| `runtime.status` | Check runtime status via boto3 |

### Workflow

```bash
make runtime.package                 # zip + upload to S3
make runtime.deploy                  # deploy CloudFormation stack
make runtime.status                  # verify runtime is READY
make runtime.invoke                  # run test script (JWT auth)
make runtime.observability           # create CloudWatch Logs delivery pipeline
make runtime.logs                    # tail application logs
```

### Packaging Details

The `runtime.package` target:
1. Installs Python dependencies for `aarch64-manylinux2014` / Python 3.12 into `tmp/runtime_package/` (117 packages including `aws-opentelemetry-distro`, all OTEL instrumentors, and `boto3`/`botocore`, ~35MB zip)
2. Copies `app/mcpserver/start.py` and `app/mcpserver/main.py` into the package directory
3. Zips the package and names it with the md5 hash of the zip (e.g., `runtime_<md5>.zip`)
4. Uploads the zip to `s3://<bucket>/<stack-name>/runtime_<md5>.zip`

The `runtime.deploy` target picks up the latest zip from `tmp/` and passes the S3 bucket and prefix as parameters to the CloudFormation template.

## Sub-Project 2, Phase 2: AgentCore Gateway

AgentCore Gateway with an MCPServer target backed by the AgentCore Runtime. Uses Cognito OAuth2 (client_credentials flow) for Gateway-to-Runtime authentication. Optionally attaches a Lambda request interceptor (Phase 3).

### Resources

| Resource | Value |
|----------|-------|
| Stack name | `interceptors-demo-gateway` |
| Gateway name | `interceptors-demo-gateway` |
| Protocol | MCP (SEMANTIC search, version 2025-03-26) |
| Client auth | NONE |
| Target auth | OAuth (Cognito client_credentials) |
| Interceptor | Lambda REQUEST interceptor (conditional on `pInterceptorArn`) |
| OAuth provider | `interceptors-demo-oauth-provider` (API-managed) |
| IaC | CloudFormation template (`gateway/iac/gateway.yaml`) + API script (`gateway/setup_oauth.py`) |

### Commands

| Target | Description |
|--------|-------------|
| `gateway.deploy` | SAM deploy the Gateway stack (Cognito + Gateway + conditional Target + conditional Interceptor) |
| `gateway.setup` | Create OAuth2 credential provider via API |
| `gateway.setup.delete` | Delete OAuth2 credential provider |
| `gateway.setup.get` | Get OAuth2 credential provider details |
| `gateway.delete` | SAM delete the Gateway stack |
| `gateway.invoke` | Test MCP flow through Gateway (initialize, tools/list, tools/call) |
| `gateway.status` | Check Gateway status via boto3 |

### Deployment Workflow (multi-step)

The Gateway requires a multi-step deployment because the GatewayTarget needs an OAuth credential provider ARN, but no CloudFormation resource exists for credential providers.

```bash
# Step 1: Deploy Gateway + Cognito (no target, no interceptor)
# Set O_CREDENTIAL_PROVIDER_ARN=NONE and O_INTERCEPTOR_ARN=NONE in environment.sh
make gateway.deploy
# Record stack outputs in environment.sh

# Step 2: Create OAuth2 credential provider (API)
make gateway.setup
# Record O_CREDENTIAL_PROVIDER_ARN in environment.sh

# Step 3: Update Runtime with JWT auth
make runtime.deploy

# Step 4: Verify Runtime with JWT auth
make runtime.invoke

# Step 5: Create CloudWatch Logs delivery pipeline for runtime observability
make runtime.observability

# Step 6: Redeploy Gateway (creates GatewayTarget with OAuth + attaches interceptor)
# Set O_CREDENTIAL_PROVIDER_ARN and O_INTERCEPTOR_ARN to real values in environment.sh
make gateway.deploy

# Step 7: Test end-to-end through Gateway
make gateway.invoke

# Step 8: Verify runtime logs
make runtime.logs
```

### Teardown

API-managed resources must be deleted before their CloudFormation stacks:

```bash
make runtime.observability.delete    # delete log delivery pipeline (API)
make gateway.setup.delete            # delete credential provider (API)
make gateway.delete                  # delete Gateway stack (CFN)
make runtime.delete                  # delete Runtime stack (CFN)
```

## Sub-Project 2, Phase 3: Request Interceptor on Gateway

The Lambda interceptor from Sub-Project 1 is attached to the Gateway via the `InterceptorConfigurations` property. The interceptor runs on every REQUEST, inspects the MCP method, and adds a custom header (`X-Amzn-Bedrock-AgentCore-Runtime-Custom-Interceptor-Demo`) only on `tools/call` requests. Other methods pass through unchanged.

The interceptor is configured conditionally: when `O_INTERCEPTOR_ARN` is set to a real Lambda ARN, it is attached; when set to `NONE`, the Gateway operates without an interceptor.

### Verification

Interceptor behavior is verified at multiple layers:

1. **Interceptor Lambda logs** (`/aws/lambda/interceptors-demo-interceptor`):
   - `initialize` and `tools/list` requests: passthrough, no header added
   - `tools/call` requests: header `X-Amzn-Bedrock-AgentCore-Runtime-Custom-Interceptor-Demo: intercepted-at-<ISO-timestamp>` added

2. **MCP server tool response** (`make gateway.invoke`):
   - The `hello_world` tool reads the custom header via `ctx.request_context.request.headers` and returns the value in the `interceptor_header` field
   - Confirms the header propagated through: Interceptor Lambda -> Gateway -> GatewayTarget -> Runtime -> MCP server

3. **Runtime application logs** (`make runtime.logs`):
   - Structured OTEL logs show each MCP method call (initialize, notifications/initialized, tools/call) with request payloads, trace IDs, and session IDs

### Header Propagation Chain

For the custom header to reach the MCP server tool handler, three configurations are required:

1. **GatewayTarget `MetadataConfiguration.AllowedRequestHeaders`** — tells the Gateway to forward the header to the target
2. **Runtime `RequestHeaderAllowlist`** — tells the Runtime to pass the header to the application container
3. **MCP server code** — reads the header via `ctx.request_context.request.headers`

Without `AllowedRequestHeaders` on the GatewayTarget, the Gateway strips the custom header even though the interceptor added it.

## Configuration

All parameters are managed in `etc/environment.sh`:

| Parameter | Description |
|-----------|-------------|
| `PROFILE` | AWS CLI profile |
| `REGION` | AWS region |
| `P_INTERCEPTOR_FUNCTION_NAME` | Lambda interceptor function name |
| `P_STACK_INTERCEPTOR` | SAM stack name for the interceptor |
| `P_RUNTIME_NAME` | AgentCore Runtime name |
| `P_STACK_RUNTIME` | SAM stack name for the runtime |
| `P_S3_BUCKET` | S3 bucket for runtime code artifacts |
| `P_GATEWAY_NAME` | AgentCore Gateway name |
| `P_STACK_GATEWAY` | SAM stack name for the gateway |
| `P_COGNITO_DOMAIN` | Cognito UserPool domain prefix (globally unique) |
| `P_OAUTH_PROVIDER_NAME` | OAuth2 credential provider name |
| `O_*` | Stack outputs (ARNs, IDs, URLs — set after deployment) |

## Header Propagation

Custom headers forwarded to AgentCore Runtime must use the prefix `X-Amzn-Bedrock-AgentCore-Runtime-Custom-`. Headers not matching this prefix are stripped by the Runtime.

For end-to-end header propagation through the Gateway:
1. **GatewayTarget `MetadataConfiguration.AllowedRequestHeaders`** — required for the Gateway to forward interceptor-added headers to the target
2. **GatewayTarget `MetadataConfiguration.AllowedResponseHeaders`** — required for the Gateway to forward response headers from the target back to the client
3. **Runtime `RequestHeaderAllowlist`** — required for the Runtime to pass headers to the application container

## Observability

AgentCore Runtime does not emit application logs to CloudWatch by default. Two log groups exist:

### Vended Delivery Pipeline (API-managed)

A CloudWatch Logs vended delivery pipeline captures structured OTEL logs at the infrastructure level — MCP request/response payloads, trace IDs, session IDs, and request IDs. This must be created via API (no CFN resource exists).

```bash
make runtime.observability           # create delivery pipeline (one-time)
make runtime.logs                    # tail application logs
make runtime.observability.delete    # cleanup before deleting runtime
```

Log group: `/aws/vendedlogs/bedrock-agentcore/runtime/APPLICATION_LOGS/<runtime-id>`

### OTEL Application Log Group

The runtime infrastructure creates a log group at `/aws/bedrock-agentcore/runtimes/<runtime-name>-<id>-DEFAULT` with two stream types:
- `otel-rt-logs` — structured OTEL log records exported by the AWS OTEL distro's `OTLPAwsLogRecordExporter` (writes directly to CloudWatch via botocore, not via localhost OTLP)
- `runtime-logs-<session-id>` — stdout/stderr from the application process (startup logs, uvicorn access logs)

The MCP server uses `start.py` to bootstrap OTEL auto-instrumentation. The `EnvironmentVariables` in the CFN template set `AGENT_OBSERVABILITY_ENABLED=true` and `AWS_REGION`.

**Prerequisites for OTEL auto-instrumentation to work:**
1. **`boto3`/`botocore` in the deployment package** — the AWS OTEL distro's `OTLPAwsLogRecordExporter` uses botocore to write logs directly to CloudWatch. Without it, the entire AWS configurator fails with `ModuleNotFoundError: No module named 'botocore'` and no OTEL telemetry is exported.
2. **`AWS_REGION` environment variable** — the AWS OTEL distro needs this to auto-configure OTLP endpoints. Without it, logs warn "AWS region could not be determined."
3. **IAM role with `logs:DescribeLogGroups` on `Resource: "*"`** — required as a separate statement (cannot be scoped to a specific log group ARN). The role also needs `CreateLogStream`, `PutLogEvents`, etc. scoped to the log group.
4. **IAM role with `xray:PutTraceSegments` and `xray:PutTelemetryRecords` on `Resource: "*"`** — the OTEL trace exporter sends spans to X-Ray. Without these permissions, trace export fails with HTTP 403.

```bash
make runtime.logs                    # tail vended delivery pipeline logs
```

Log group: `/aws/bedrock-agentcore/runtimes/<runtime-name>-<id>-DEFAULT`

## Known Issues

1. **SigV4/JWT mutual exclusivity**: When JWT auth is configured on the Runtime, the SDK's `invoke_agent_runtime` (SigV4) no longer works. Use `test_runtime.py --jwt` for direct HTTP invocation with Bearer tokens.

2. **Cognito aud claim**: Cognito access tokens from `client_credentials` grant lack an `aud` claim. Do not set `AllowedAudience` on the runtime's JWT authorizer — use `AllowedClients` only.

3. **Gateway role requires `agent-credential-provider:*`**: The Gateway role needs the `agent-credential-provider:*` IAM action namespace (in addition to `bedrock-agentcore:*`) for the OAuth token exchange to work. Without it, `tools/call` fails with "An internal error occurred" while `initialize` and `tools/list` succeed (served from cache).

4. **Gateway `SearchType: SEMANTIC` requires no targets**: The Gateway's `SearchType` cannot be changed while targets exist. To update, delete the target first (deploy with `pCredentialProviderArn=NONE`), update the Gateway, then recreate the target.

## References

- [Using interceptors with Gateway](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-interceptors.html)
- [Gateway target MCPServers](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-target-MCPservers.html)
- [Header propagation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-headers.html)
- [Runtime header allowlist](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-header-allowlist.html)
- [CFN: AWS::BedrockAgentCore::Gateway](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-bedrockagentcore-gateway.html)
- [CFN: Gateway InterceptorConfiguration](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-properties-bedrockagentcore-gateway-interceptorconfiguration.html)
- [CFN: AWS::BedrockAgentCore::GatewayTarget](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-bedrockagentcore-gatewaytarget.html)
- [CFN: AWS::BedrockAgentCore::Runtime](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-bedrockagentcore-runtime.html)
- [Runtime observability](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-configure.html)
