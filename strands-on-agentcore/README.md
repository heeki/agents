# Strands Agents on AgentCore

This repository contains two deployment options for deploying on Amazon Bedrock AgentCore:
- Strands Agent (HTTP)
- MCP Server (JWT-protected)

## Project Structure

```
agents/
├── README.md
└── strands-on-agentcore/
    ├── agent/
    │   └── strands.py                     # Strands Agent entrypoint
    ├── etc/
    │   ├── environment.template.mcp       # MCP Server environment template
    │   ├── environment.template.strands   # Strands Agent environment template
    │   └── environment.sh                 # Active environment loaded by Makefile
    ├── iac/                               # Infrastructure as Code
    │   ├── cognito.yaml                   # Cognito User Pool for MCP
    │   ├── deploy.py                      # AgentCore control/data plane helper
    │   ├── infrastructure.yaml            # AgentCore runtime infrastructure
    │   └── generate_secrethash.py         # Cognito secret hash generator
    ├── mcp/
    │   └── client.py                      # Simple MCP client (Streamable HTTP)
    │   └── server.py                      # Simple MCP server (Streamable HTTP)
    ├── dockerfile.strands                 # Strands Agent container
    ├── dockerfile.mcp                     # MCP Server container
    ├── pyproject.toml
    └── requirements.txt

```

## Prerequisites

- Python 3.12+
- Docker/Podman
- AWS CLI configured with a profile that has access to Bedrock AgentCore, Cognito, CloudFormation, ECR

## Choose Your Deployment Path

Copy ONE template to `etc/environment.sh` before running any Make targets.

### 1) Strands Agent (HTTP)

1. Initialize environment
   ```bash
   cd strands-on-agentcore
   uv pip install -r requirements.txt
   cp etc/environment.template.strands etc/environment.sh
   # edit etc/environment.sh with your values
   ```

2. Deploy infrastructure resources
   ```bash
   make infrastructure
   # update outputs for O_ECR_REPO, O_ECR_REPO_ARN, O_ECR_REPO_URI, O_AGENT_ROLE
   ```

3. Build and publish container (uses `C_DOCKERFILE=dockerfile.strands`)
   ```bash
   make podman
   ```

4. Create or update AgentCore runtime
   ```bash
   make agentcore.create   # once, can also be used to get the Runtime ARN
   make agentcore.update   # on image updates (increment C_VERSION first)
   # update outputs for O_AGENT_ARN, O_AGENT_ID
   ```

5. Invoke the agent
   ```bash
   make agentcore.invoke
   ```

6. [Optional] Run locally without AgentCore
   ```bash
   make local.agent
   make local.podman
   ```

### 2) MCP Server (JWT)

1. Initialize environment
   ```bash
   cd strands-on-agentcore
   uv pip install -r requirements.txt
   cp etc/environment.template.mcp etc/environment.sh
   # edit etc/environment.sh with your values
   ```

2. Deploy infrastructure resources
   ```bash
   make infrastructure
   # update outputs for O_ECR_REPO, O_ECR_REPO_ARN, O_ECR_REPO_URI, O_AGENT_ROLE
   ```

3. Deploy Cognito (User Pool + Client + Resource Server)
   ```bash
   make cognito
   # update outputs for O_COGNITO_USERPOOL, O_COGNITO_PROVIDERNAME, O_COGNITO_PROVIDERURL, O_COGNITO_CLIENTID, O_COGNITO_CLIENTSECRET
   ```

4. Initialize the Cognito user and set a permanent password
   - A temporary password will be emailed to `P_COGNITO_USEREMAIL` by the stack
   - Set in `etc/environment.sh`:
     - `P_COGNITO_USERTEMPPW` with the emailed temporary password
     - `P_COGNITO_USERPERMPW` with your chosen permanent password

   Generate the Cognito secret hash using the helper script:
   ```bash
   cognito.secrethash
   # copy the output of SECRETHASH into P_COGNITO_SECRETHASH in etc/environment.sh
   ```

   Update the password using admin auth challenges:
   ```bash
   cognito.admin
   cognito.updatepw
   ```

5. Obtain an access token and set `BEARER_TOKEN`. Use the OAuth2 client credentials flow against the Cognito token endpoint with your custom Resource Server scope (e.g., `${P_COGNITO_RESOURCE_SERVER_IDENTIFIER}/mcp_echo`).
   ```bash
   cognito.client_credentials
   ```
   Persist the access token in `etc/environment.sh` by setting `BEARER_TOKEN`.

6. Build and publish the MCP container (uses `C_DOCKERFILE=dockerfile.mcp`)
   ```bash
   make podman
   ```

7. Create or update the MCP AgentCore runtime
   ```bash
   make agentcore.create   # once, can also be used to get the Runtime ARN
   make agentcore.update   # on image updates (increment C_VERSION first)
   ```

8. Test the MCP runtime with the local client
   ```bash
   # requires AGENT_ARN and BEARER_TOKEN to be exported (set in environment file)
   make local.mcp.client
   ```

## Notes on Configuration

Important environment variables are provided in the templates and include:
- **AWSCLI**: `PROFILE`, `REGION`, `BUCKET`, `ACCOUNTID`
- **ECR**: `C_DOCKERFILE`, `C_REPO_BASE`, `C_REPO_IMAGE`, `C_VERSION`, `C_REPO_URI`
- **AgentCore**: `EXECUTION_ROLE`, `AGENT_NAME`, `SERVER_PROTOCOL`, `ENV_VARS`
- **Cognito**: `P_COGNITO_*`, `O_COGNITO_*`, `P_COGNITO_SECRETHASH`, `P_COGNITO_TOKEN_URL`
- **Langfuse (optional)**: `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`
- **Invocation**: `O_AGENT_ARN`, `O_AGENT_VERSION`, `P_PROMPT`

Increment `C_VERSION` for each new image you push to ensure runtime updates pick up the latest image.

## Make Targets

Common targets (respect `etc/environment.sh`):
- `make infrastructure` - create agent IAM role and ECR repository
- `make cognito` - create Cognito user pool, resource server, and client id
- `make podman` — build, tag, and push image to ECR
- `make local.agent` — run Strands app locally
- `make local.podman` — run Strands app or MCP server locally via the built container
- `make local.mcp` — run MCP server locally
- `make local.mcp.client` - run the MCP test client
- `make inspector` - run MCP inspector for local MCP testing
- `make agentcore.create` — create AgentCore runtime
- `make agentcore.update` — update AgentCore runtime
- `make agentcore.invoke` — invoke runtime (HTTP/Strands path)
