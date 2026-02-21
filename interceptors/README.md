# Interceptors Prototype

Demonstrates Lambda-based request interceptors on AgentCore Gateway. The interceptor adds a custom HTTP header (`X-Amzn-Bedrock-AgentCore-Runtime-Custom-Interceptor-Demo`) to MCP `tools/call` requests, and the downstream MCP server logs the header to prove the transformation worked.

## Deployed Configurations

### Sub-Project 1: Lambda Interceptor

| Resource | Value |
|----------|-------|
| Stack name | `interceptors-demo-interceptor` |
| Region | `us-east-1` |
| Lambda function | `interceptors-demo-interceptor` |
| Gateway service role | `interceptors-demo-interceptor-gateway-role` |

### Makefile Targets

| Target | Description |
|--------|-------------|
| `interceptor.build` | SAM build the interceptor Lambda |
| `interceptor.deploy` | SAM deploy the interceptor stack |
| `interceptor.delete` | SAM delete the interceptor stack |
| `interceptor.local.tools_call` | Local test with `tools/call` event (header injected) |
| `interceptor.local.tools_list` | Local test with `tools/list` event (passthrough) |
