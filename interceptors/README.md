# Interceptors Prototype

Demonstrates Lambda-based request interceptors on AgentCore Gateway. The interceptor adds a custom HTTP header (`X-Amzn-Bedrock-AgentCore-Runtime-Custom-Interceptor-Demo`) to MCP `tools/call` requests, and the downstream MCP server logs the header to prove the transformation worked.

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
                              |        On other methods: passes through unchanged
                              |
                              +--> AgentCore Runtime (MCP Server)
                                       Logs custom header + full payload
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
    mcpserver/                        # Sub-project 2: MCP server
      main.py                         # FastMCP hello_world server
      requirements.txt                # Python dependencies (mcp[cli])
      test_runtime.py                 # Test script for invoking deployed runtime
      iac/
        runtime.yaml                  # CloudFormation template (AgentCore Runtime + IAM role)
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

## Sub-Project 2: MCP Server on AgentCore Runtime

Stateless MCP server deployed to AgentCore Runtime via CloudFormation. Exposes a `hello_world` tool and accepts the custom interceptor header via an allowlist.

### Resources

| Resource | Value |
|----------|-------|
| Stack name | `interceptors-demo-runtime` |
| Runtime name | `interceptors_demo_mcpserver` |
| Protocol | MCP (stateless streamable-http) |
| Network | PUBLIC |
| Header allowlist | `X-Amzn-Bedrock-AgentCore-Runtime-Custom-Interceptor-Demo` |
| IaC | CloudFormation template (`app/mcpserver/iac/runtime.yaml`) |

### Commands

| Target | Description |
|--------|-------------|
| `runtime.package` | Zip dependencies + code to `tmp/`, upload to S3 with md5-based name |
| `runtime.deploy` | SAM deploy the AgentCore Runtime stack (references S3 artifact) |
| `runtime.delete` | SAM delete the AgentCore Runtime stack |
| `runtime.invoke` | Test the deployed runtime (initialize, tools/list, tools/call) |
| `runtime.status` | Check runtime status via boto3 |

### Workflow

```bash
make runtime.package                 # zip + upload to S3
make runtime.deploy                  # deploy CloudFormation stack
make runtime.status                  # verify runtime is READY
make runtime.invoke                  # run test script against deployed runtime
```

### Packaging Details

The `runtime.package` target:
1. Installs Python dependencies for `aarch64-manylinux2014` / Python 3.12 into `tmp/runtime_package/`
2. Copies `app/mcpserver/main.py` into the package directory
3. Zips the package and names it with the md5 hash of the zip (e.g., `runtime_<md5>.zip`)
4. Uploads the zip to `s3://<bucket>/<stack-name>/runtime_<md5>.zip`

The `runtime.deploy` target picks up the latest zip from `tmp/` and passes the S3 bucket and prefix as parameters to the CloudFormation template.

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
| `O_INTERCEPTOR_ARN` | Lambda interceptor ARN (from stack outputs) |
| `O_GATEWAY_ROLE_ARN` | Gateway service role ARN (from stack outputs) |
| `O_RUNTIME_ARN` | AgentCore Runtime ARN (from stack outputs) |
| `O_RUNTIME_ID` | AgentCore Runtime ID (from stack outputs) |

## Header Propagation

Custom headers forwarded to AgentCore Runtime must use the prefix `X-Amzn-Bedrock-AgentCore-Runtime-Custom-`. Headers not matching this prefix are stripped by the Runtime.

The runtime's `RequestHeaderAllowlist` in `runtime.yaml` must explicitly include any custom headers the interceptor injects.

## References

- [Using interceptors with Gateway](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-interceptors.html)
- [Interceptor configuration](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-interceptors-configuration.html)
- [Interceptor examples](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-interceptors-examples.html)
- [Header propagation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-headers.html)
- [Runtime header allowlist](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-header-allowlist.html)
- [CloudFormation: AWS::BedrockAgentCore::Runtime](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-bedrockagentcore-runtime.html)
