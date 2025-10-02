include etc/environment.sh

# infrastructure
infrastructure: infrastructure.package infrastructure.deploy
infrastructure.package:
	sam package --profile ${PROFILE} -t ${INFRASTRUCTURE_TEMPLATE} --output-template-file ${INFRASTRUCTURE_OUTPUT} --s3-bucket ${BUCKET} --s3-prefix ${INFRASTRUCTURE_STACK}
infrastructure.deploy:
	sam deploy --profile ${PROFILE} -t ${INFRASTRUCTURE_OUTPUT} --stack-name ${INFRASTRUCTURE_STACK} --parameter-overrides ${INFRASTRUCTURE_PARAMS} --capabilities CAPABILITY_NAMED_IAM

# cognito
cognito: cognito.package cognito.deploy
cognito.package:
	sam package -t ${COGNITO_TEMPLATE} --output-template-file ${COGNITO_OUTPUT} --s3-bucket ${BUCKET} --s3-prefix ${COGNITO_STACK}
cognito.deploy:
	sam deploy -t ${COGNITO_OUTPUT} --region ${REGION} --stack-name ${COGNITO_STACK} --parameter-overrides ${COGNITO_PARAMS} --capabilities CAPABILITY_NAMED_IAM
cognito.delete:
	sam delete --stack-name ${COGNITO_STACK}
cognito.secrethash:
	uv run iac/generate_secrethash.py ${P_COGNITO_USERNAME} ${O_COGNITO_CLIENTID} ${O_COGNITO_CLIENTSECRET}
cognito.admin:
	aws --profile ${PROFILE} cognito-idp admin-initiate-auth --user-pool-id ${O_COGNITO_USERPOOL} --client-id ${O_COGNITO_CLIENTID} --auth-flow ADMIN_NO_SRP_AUTH --auth-parameters SECRET_HASH="${P_COGNITO_SECRETHASH}",USERNAME="${P_COGNITO_USERNAME}",PASSWORD="${P_COGNITO_USERTEMPPW}" | jq | tee tmp/cognito_admin.json | jq
cognito.updatepw:
	aws --profile ${PROFILE} cognito-idp admin-respond-to-auth-challenge --user-pool-id ${O_COGNITO_USERPOOL} --client-id ${O_COGNITO_CLIENTID} --challenge-name NEW_PASSWORD_REQUIRED --challenge-responses SECRET_HASH="${P_COGNITO_SECRETHASH}",USERNAME="${P_COGNITO_USERNAME}",NEW_PASSWORD="${P_COGNITO_USERPERMPW}" --session `cat tmp/cognito_admin.json | jq -r .Session` | jq | tee tmp/cognito_updatepw.json | jq
cognito.login:
	aws --profile ${PROFILE} cognito-idp initiate-auth --client-id ${O_COGNITO_CLIENTID} --auth-flow USER_PASSWORD_AUTH --auth-parameters SECRET_HASH="${P_COGNITO_SECRETHASH}",USERNAME="${P_COGNITO_USERNAME}",PASSWORD="${P_COGNITO_USERPERMPW}" | jq | tee tmp/cognito_login.json | jq
cognito.login.nosecret:
	aws --profile ${PROFILE} cognito-idp initiate-auth --client-id ${O_COGNITO_CLIENTID} --auth-flow USER_PASSWORD_AUTH --auth-parameters USERNAME="${P_COGNITO_USERNAME}",PASSWORD="${P_COGNITO_USERPERMPW}" | jq | tee tmp/cognito_login.json | jq
cognito.client_credentials:
	curl -s -X POST ${P_COGNITO_TOKEN_URL} \
	-H "Content-Type: application/x-www-form-urlencoded" \
	-d grant_type=client_credentials \
	-d client_id=${O_COGNITO_CLIENTID} \
	-d client_secret=${O_COGNITO_CLIENTSECRET} \
	-d "scope=mcp.heeki.cloud/agentcore:mcp_echo" | jq

# agent packaging
podman: podman.build podman.login podman.tag podman.push
podman.build:
	podman build --platform ${PLATFORM_DEPLOY} -f ${C_DOCKERFILE} -t ${C_TAG} .
podman.login:
	aws ecr --profile ${PROFILE} get-login-password --region ${REGION} | podman login --username AWS --password-stdin ${C_REPO_BASE}
podman.tag:
	podman tag ${C_TAG} ${C_REPO_URI}
podman.push:
	podman push ${C_REPO_URI}

# local testing
local.agent:
	uv run agent/app.py
local.agent.memory:
	uv run agent/app_memory.py
local.podman:
	podman run --platform ${PLATFORM_DEPLOY} -p ${HOST_PORT}:${CONTAINER_PORT} --env-file etc/environment.docker \
		-v ${HOME}/.aws:/home/bedrock_agentcore/.aws:ro \
		-e AWS_PROFILE=${PROFILE} \
		${C_TAG}
local.podman.clean:
	podman container prune -f || true
local.test:
	curl -X POST http://localhost:8080/invocations -H "Content-Type: application/json" -d '{"prompt": "What is VO2 max? What is the best way to improve it?"}'
local.test.memory1:
	curl -X POST http://localhost:8080/invocations -H "Content-Type: application/json" -d '{"prompt": "My name is ${USER_ID}. What is VO2 max? What is the best way to improve it?"}'
local.test.memory2:
	curl -X POST http://localhost:8080/invocations -H "Content-Type: application/json" -d '{"prompt": "What are the ranges of values? What is good for a non-professional but active runner?"}'
local.test.memory3:
	curl -X POST http://localhost:8080/invocations -H "Content-Type: application/json" -d '{"prompt": "What is my name again?"}'

# mcp testing
local.mcp:
	uv run mcp/server.py
local.mcp.client:
	uv run mcp/client.py
inspector:
	npx @modelcontextprotocol/inspector

# agentcore iac deployment
runtime: runtime.package runtime.deploy
runtime.package:
	sam package --profile ${PROFILE} --region ${REGION} -t ${RUNTIME_TEMPLATE} --output-template-file ${RUNTIME_OUTPUT} --s3-bucket ${BUCKET} --s3-prefix ${RUNTIME_STACK}
runtime.deploy:
	sam deploy --profile ${PROFILE} --region ${REGION} -t ${RUNTIME_OUTPUT} --stack-name ${RUNTIME_STACK} --parameter-overrides ${RUNTIME_PARAMS} --capabilities CAPABILITY_NAMED_IAM
runtime.delete:
	sam delete --stack-name ${RUNTIME_STACK}

# optional flags
ENV_VARS_FLAG := $(if $(strip $(ENV_VARS)),--env-vars ${ENV_VARS},)
AUTHORIZE_FLAG := $(if $(strip $(AUTHORIZER_CONFIGURATION)),--authorizer-configuration ${AUTHORIZER_CONFIGURATION},)

# agentcore scripted deployment
agentcore.create:
	uv run iac/deploy.py --action create --runtime-name ${AGENT_NAME} --ecr-repo-uri ${C_REPO_URI} --execution-role ${EXECUTION_ROLE} --server-protocol ${SERVER_PROTOCOL} ${ENV_VARS_FLAG} ${AUTHORIZE_FLAG}
agentcore.update:
	uv run iac/deploy.py --action update --runtime-id ${O_AGENT_ID} --ecr-repo-uri ${C_REPO_URI} --execution-role ${EXECUTION_ROLE} --server-protocol ${SERVER_PROTOCOL} ${ENV_VARS_FLAG} ${AUTHORIZE_FLAG}
agentcore.invoke:
	uv run iac/deploy.py --action invoke --agent-arn ${O_AGENT_ARN} --agent-version ${O_AGENT_QUALIFIER} --prompt ${P_PROMPT}
