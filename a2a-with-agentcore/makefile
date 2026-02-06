include etc/environment.sh

# ============================================================================
# INFRASTRUCTURE
# ============================================================================
infrastructure: infrastructure.package infrastructure.deploy
infrastructure.package:
	sam package --profile ${PROFILE} -t ${INFRASTRUCTURE_TEMPLATE} --output-template-file ${INFRASTRUCTURE_OUTPUT} --s3-bucket ${BUCKET} --s3-prefix ${INFRASTRUCTURE_STACK}
infrastructure.deploy:
	sam deploy --profile ${PROFILE} -t ${INFRASTRUCTURE_OUTPUT} --stack-name ${INFRASTRUCTURE_STACK} --parameter-overrides ${INFRASTRUCTURE_PARAMS} --capabilities CAPABILITY_NAMED_IAM

# ============================================================================
# COGNITO
# ============================================================================
cognito: cognito.package cognito.deploy
cognito.package:
	sam package --profile ${PROFILE} -t ${COGNITO_TEMPLATE} --output-template-file ${COGNITO_OUTPUT} --s3-bucket ${BUCKET} --s3-prefix ${COGNITO_STACK}
cognito.deploy:
	sam deploy --profile ${PROFILE} -t ${COGNITO_OUTPUT} --stack-name ${COGNITO_STACK} --parameter-overrides ${COGNITO_PARAMS} --capabilities CAPABILITY_NAMED_IAM
cognito.delete:
	sam delete --profile ${PROFILE} --stack-name ${COGNITO_STACK}
cognito.secrethash:
	uv run iac/generate_secrethash.py ${P_COGNITO_USERNAME} ${O_COGNITO_CLIENTID} ${O_COGNITO_CLIENTSECRET}
cognito.login:
	aws --profile ${PROFILE} cognito-idp initiate-auth --client-id ${O_COGNITO_CLIENTID} --auth-flow USER_PASSWORD_AUTH --auth-parameters SECRET_HASH="${P_COGNITO_SECRETHASH}",USERNAME="${P_COGNITO_USERNAME}",PASSWORD="${P_COGNITO_USERPERMPW}" | jq | tee tmp/cognito_login.json

# ============================================================================
# API GATEWAY
# ============================================================================
apigw: apigw.package apigw.deploy
apigw.package:
	sam package --profile ${PROFILE} -t ${APIGW_TEMPLATE} --output-template-file ${APIGW_OUTPUT} --s3-bucket ${BUCKET} --s3-prefix ${APIGW_STACK}
apigw.deploy:
	sam deploy --profile ${PROFILE} -t ${APIGW_OUTPUT} --stack-name ${APIGW_STACK} --parameter-overrides ${APIGW_PARAMS} --capabilities CAPABILITY_NAMED_IAM
apigw.delete:
	sam delete --profile ${PROFILE} --stack-name ${APIGW_STACK}

# ============================================================================
# AGENTCORE RUNTIMES (CloudFormation)
# ============================================================================
agentcore: agentcore.package agentcore.deploy
agentcore.package:
	sam package --profile ${PROFILE} -t ${AGENTCORE_TEMPLATE} --output-template-file ${AGENTCORE_OUTPUT} --s3-bucket ${BUCKET} --s3-prefix ${AGENTCORE_STACK}
agentcore.deploy:
	sam deploy --profile ${PROFILE} -t ${AGENTCORE_OUTPUT} --stack-name ${AGENTCORE_STACK} --parameter-overrides ${AGENTCORE_PARAMS} --capabilities CAPABILITY_NAMED_IAM
agentcore.update:
	sam deploy --profile ${PROFILE} -t ${AGENTCORE_OUTPUT} --stack-name ${AGENTCORE_STACK} --parameter-overrides ${AGENTCORE_PARAMS} --capabilities CAPABILITY_NAMED_IAM --no-fail-on-empty-changeset
agentcore.delete:
	sam delete --profile ${PROFILE} --stack-name ${AGENTCORE_STACK} --no-prompts

# ============================================================================
# CONTAINER BUILD - ORCHESTRATOR (Python/Strands)
# ============================================================================
orchestrator.build:
	podman build --platform ${PLATFORM_DEPLOY} -f ${ORCHESTRATOR_DOCKERFILE} -t ${ORCHESTRATOR_TAG} .
orchestrator.login:
	aws ecr --profile ${PROFILE} get-login-password --region ${REGION} | podman login --username AWS --password-stdin ${C_REPO_BASE}
orchestrator.tag:
	podman tag ${ORCHESTRATOR_TAG} ${ORCHESTRATOR_URI}
orchestrator.push: orchestrator.login orchestrator.tag
	podman push ${ORCHESTRATOR_URI}
# Orchestrator deployment now handled by agentcore CloudFormation stack

# ============================================================================
# CONTAINER BUILD - BIOMECHANICS LAB (TypeScript/LangGraph)
# ============================================================================
biomechanics.build:
	podman build --platform ${PLATFORM_DEPLOY} -f ${BIOMECHANICS_DOCKERFILE} -t ${BIOMECHANICS_TAG} .
biomechanics.login:
	aws ecr --profile ${PROFILE} get-login-password --region ${REGION} | podman login --username AWS --password-stdin ${C_REPO_BASE}
biomechanics.tag:
	podman tag ${BIOMECHANICS_TAG} ${BIOMECHANICS_URI}
biomechanics.push: biomechanics.login biomechanics.tag
	podman push ${BIOMECHANICS_URI}
# Biomechanics deployment now handled by agentcore CloudFormation stack

# ============================================================================
# CONTAINER BUILD - LIFE SYNC (Python/LangGraph)
# ============================================================================
lifesync.build:
	podman build --platform ${PLATFORM_DEPLOY} -f ${LIFESYNC_DOCKERFILE} -t ${LIFESYNC_TAG} .
lifesync.login:
	aws ecr --profile ${PROFILE} get-login-password --region ${REGION} | podman login --username AWS --password-stdin ${C_REPO_BASE}
lifesync.tag:
	podman tag ${LIFESYNC_TAG} ${LIFESYNC_URI}
lifesync.push: lifesync.login lifesync.tag
	podman push ${LIFESYNC_URI}
# Life Sync deployment now handled by agentcore CloudFormation stack

# ============================================================================
# BUILD ALL
# ============================================================================
build.all: orchestrator.build biomechanics.build lifesync.build
push.all: orchestrator.push biomechanics.push lifesync.push
# Deploy all agent containers and AgentCore runtimes
deploy.all: containers.push agentcore.deploy

# Build and push all containers
containers.push: orchestrator.push biomechanics.push lifesync.push

# ============================================================================
# LOCAL DEVELOPMENT
# ============================================================================
local.orchestrator:
	cd agents/orchestrator && PYTHONPATH=. uv run python app.py

local.biomechanics:
	cd agents/biomechanics-lab && npm run dev

local.lifesync:
	cd agents/life-sync && PYTHONPATH=src uv run python src/app.py

# Podman Compose commands
local.compose.build:
	podman-compose -f docker/docker-compose.yaml build

local.compose.up:
	podman-compose -f docker/docker-compose.yaml up -d

local.compose.up.build:
	podman-compose -f docker/docker-compose.yaml up -d --build

local.compose.down:
	podman-compose -f docker/docker-compose.yaml down

local.compose.down.volumes:
	podman-compose -f docker/docker-compose.yaml down -v

local.compose.logs:
	podman-compose -f docker/docker-compose.yaml logs -f

local.compose.ps:
	podman-compose -f docker/docker-compose.yaml ps

local.compose.restart:
	podman-compose -f docker/docker-compose.yaml restart

# ============================================================================
# TESTING
# ============================================================================
test.unit.orchestrator:
	cd agents/orchestrator && PYTHONPATH=. uv run pytest tests/ -v

test.unit.biomechanics:
	cd agents/biomechanics-lab && npm test

test.unit.lifesync:
	cd agents/life-sync && PYTHONPATH=. uv run pytest tests/ -v

test.unit: test.unit.orchestrator test.unit.biomechanics test.unit.lifesync

test.integration:
	PYTHONPATH=. uv run python tests/integration/test_a2a_flow.py

# ============================================================================
# INVOCATION (A2A JSON-RPC)
# ============================================================================
invoke.local:
	@curl -s -X POST http://localhost:${ORCHESTRATOR_PORT}/ \
		-H "Content-Type: application/json" \
		-d '{"jsonrpc":"2.0","id":"1","method":"tasks/send","params":{"task":{"id":"task-1","message":{"role":"user","parts":[{"type":"text","text":"Create a quick upper body workout"}]}}}}' | jq

invoke.local.full:
	@curl -s -X POST http://localhost:${ORCHESTRATOR_PORT}/ \
		-H "Content-Type: application/json" \
		-d '{"jsonrpc":"2.0","id":"1","method":"tasks/send","params":{"task":{"id":"task-1","message":{"role":"user","parts":[{"type":"text","text":"I want a strength workout for my upper body. I have about an hour and access to a full gym."}]}}}}' | jq

invoke.local.conflict:
	@curl -s -X POST http://localhost:${ORCHESTRATOR_PORT}/ \
		-H "Content-Type: application/json" \
		-d '{"jsonrpc":"2.0","id":"1","method":"tasks/send","params":{"task":{"id":"task-1","message":{"role":"user","parts":[{"type":"text","text":"I need a hypertrophy workout but I only have 25 minutes and I am at home with just dumbbells."}]}}}}' | jq

invoke.agentcard:
	@curl -s http://localhost:${ORCHESTRATOR_PORT}/.well-known/agent.json | jq

# ============================================================================
# AGENT SETUP
# ============================================================================
setup.orchestrator:
	cd agents/orchestrator && uv venv && uv pip install -r requirements.txt

setup.biomechanics:
	cd agents/biomechanics-lab && npm install

setup.lifesync:
	cd agents/life-sync && uv venv && uv pip install -r requirements.txt

setup.all: setup.orchestrator setup.biomechanics setup.lifesync

# ============================================================================
# FRONTEND
# ============================================================================
frontend.setup:
	cd frontend && uv venv && uv pip install -r requirements.txt

frontend.run:
	cd frontend && uv run streamlit run app.py

frontend.dev: frontend.run

# ============================================================================
# CLEANUP
# ============================================================================
clean:
	rm -rf agents/orchestrator/.venv
	rm -rf agents/biomechanics-lab/node_modules
	rm -rf agents/life-sync/.venv
	rm -rf frontend/.venv
	rm -rf iac/*_output.yaml
