include etc/environment.sh

# infrastructure
infrastructure: infrastructure.package infrastructure.deploy
infrastructure.package:
	sam package --profile ${PROFILE} -t ${INFRASTRUCTURE_TEMPLATE} --output-template-file ${INFRASTRUCTURE_OUTPUT} --s3-bucket ${BUCKET} --s3-prefix ${INFRASTRUCTURE_STACK}
infrastructure.deploy:
	sam deploy --profile ${PROFILE} -t ${INFRASTRUCTURE_OUTPUT} --stack-name ${INFRASTRUCTURE_STACK} --parameter-overrides ${INFRASTRUCTURE_PARAMS} --capabilities CAPABILITY_NAMED_IAM

# agent packaging
podman: podman.build podman.login podman.tag podman.push
podman.build:
	podman build --platform ${PLATFORM_DEPLOY} -f Dockerfile -t ${C_TAG} .
podman.login:
	aws ecr --profile ${PROFILE} get-login-password --region ${REGION} | podman login --username AWS --password-stdin ${C_REPO_BASE}
podman.tag:
	podman tag ${C_TAG} ${C_REPO_URI}
podman.push:
	podman push ${C_REPO_URI}

# local testing
local.agent:
	uv run src/agent.py
local.podman:
	podman run --platform ${PLATFORM_DEPLOY} -p 8080:8080 --env-file etc/environment.docker \
		-v ${HOME}/.aws:/home/bedrock_agentcore/.aws:ro \
		-e AWS_PROFILE=${PROFILE} \
		${C_TAG}
local.podman.clean:
	podman container prune -f || true
local.test:
	curl -X POST http://localhost:8080/invocations -H "Content-Type: application/json" -d '{"prompt": "Hello world!"}'

# agentcore
agentcore.create:
	uv run iac/deploy.py --action create --runtime-name ${AGENT_NAME} --ecr-repo-uri ${C_REPO_URI} --execution-role ${EXECUTION_ROLE}
agentcore.invoke:
	uv run iac/deploy.py --action invoke --agent-arn ${O_AGENT_ARN} --agent-version ${O_AGENT_VERSION} --prompt ${P_PROMPT}
