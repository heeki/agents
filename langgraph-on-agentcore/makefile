include etc/environment.sh

# local testing
local.agent:
	uv run agent/app.py

# mcp testing
local.mcp:
	uv run mcp/server.py
inspector:
	npx @modelcontextprotocol/inspector

# agentcore
agentcore.create:
	uv run iac/deploy.py --action create --runtime-name ${AGENT_NAME} --ecr-repo-uri ${C_REPO_URI} --execution-role ${EXECUTION_ROLE} --server-protocol ${SERVER_PROTOCOL} ${ENV_VARS_FLAG} ${AUTHORIZE_FLAG}
agentcore.update:
	uv run iac/deploy.py --action update --runtime-id ${O_AGENT_ID} --ecr-repo-uri ${C_REPO_URI} --execution-role ${EXECUTION_ROLE} --server-protocol ${SERVER_PROTOCOL} ${ENV_VARS_FLAG} ${AUTHORIZE_FLAG}
agentcore.invoke:
	uv run iac/deploy.py --action invoke --agent-arn ${O_AGENT_ARN} --agent-version ${O_AGENT_VERSION} --prompt ${P_PROMPT}
