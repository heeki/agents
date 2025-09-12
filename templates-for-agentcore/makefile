include etc/environment.sh

# infrastructure for api gateway
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

# api gateway
apigw: apigw.package apigw.deploy
apigw.package:
	sam package -t ${APIGW_TEMPLATE} --output-template-file ${APIGW_OUTPUT} --s3-bucket ${BUCKET} --s3-prefix ${APIGW_STACK}
apigw.deploy:
	sam deploy -t ${APIGW_OUTPUT} --region ${REGION} --stack-name ${APIGW_STACK} --parameter-overrides ${APIGW_PARAMS} --capabilities CAPABILITY_NAMED_IAM
apigw.delete:
	sam delete --stack-name ${APIGW_STACK}

# local testing
sam.local.api:
	sam local start-api -t ${APIGW_TEMPLATE} --parameter-overrides ${APIGW_PARAMS} --env-vars etc/envvars.json
sam.local.api.build:
	sam build --profile ${PROFILE} --template ${APIGW_TEMPLATE} --parameter-overrides ${APIGW_PARAMS} --build-dir build --manifest requirements.txt --use-container
	sam local start-api -t build/template.yaml --parameter-overrides ${APIGW_PARAMS} --env-vars etc/envvars.json
sam.local.invoke:
	sam local invoke -t ${APIGW_TEMPLATE} --parameter-overrides ${APIGW_PARAMS} --env-vars etc/envvars.json -e etc/event.json Fn | jq

# testing deployed resources
lambda.invoke.sync:
	aws --profile ${PROFILE} lambda invoke --function-name ${O_FN} --invocation-type RequestResponse --payload file://etc/event.json --cli-binary-format raw-in-base64-out --log-type Tail tmp/fn.json | jq "." > tmp/response.json
	cat tmp/response.json | jq -r ".LogResult" | base64 --decode
	cat tmp/fn.json | jq
lambda.invoke.async:
	aws --profile ${PROFILE} lambda invoke --function-name ${O_FN} --invocation-type Event --payload file://etc/event.json --cli-binary-format raw-in-base64-out --log-type Tail tmp/fn.json | jq "."
curl.apigw:
	curl -s -X POST ${O_API_ENDPOINT} -H "Content-Type: application/json" -d '{"prompt": "What is VO2 max? What is the best way to improve it?"}' | jq 'del(.multiValueHeaders)'
curl.apigw.auth:
	curl -s -X POST ${O_API_ENDPOINT} -H "Content-Type: application/json" -H "Authorization: Bearer ${O_COGNITO_ID_TOKEN}" -d '{"prompt": "What is VO2 max? What is the best way to improve it?"}' | jq 'del(.multiValueHeaders)'

# optional flags
ENV_VARS_FLAG := $(if $(strip $(ENV_VARS)),--env-vars ${ENV_VARS},)
AUTHORIZE_FLAG := $(if $(strip $(AUTHORIZER_CONFIGURATION)),--authorizer-configuration ${AUTHORIZER_CONFIGURATION},)

# agentcore
agentcore.gateway.create:
	uv run iac/deploy_gateway.py --action gateway.create --gateway-name ${GATEWAY_NAME} --gateway-description '${GATEWAY_DESCRIPTION}' --execution-role ${GATEWAY_EXECUTION_ROLE} ${AUTHORIZE_FLAG}
agentcore.gateway.update:
	uv run iac/deploy_gateway.py --action gateway.update --gateway-id ${O_GATEWAY_ID} --gateway-name ${GATEWAY_NAME} --gateway-description '${GATEWAY_DESCRIPTION}' --execution-role ${GATEWAY_EXECUTION_ROLE} ${AUTHORIZE_FLAG}
agentcore.target.create:
	uv run iac/deploy_gateway.py --action target.create --gateway-id ${O_GATEWAY_ID} --target-name ${TARGET_NAME} --target-description '${TARGET_DESCRIPTION}' --openapi-file ${OPENAPI_FILE} --credential-provider-inputs ${CREDENTIAL_PROVIDER_INPUTS}
agentcore.target.update:
	uv run iac/deploy_gateway.py --action target.update --gateway-id ${O_GATEWAY_ID} --target-id ${O_TARGET_ID}  --target-name ${TARGET_NAME} --target-description '${TARGET_DESCRIPTION}' --openapi-file ${OPENAPI_FILE} --credential-provider-inputs ${CREDENTIAL_PROVIDER_INPUTS}

# local testing
local.agent:
	uv run agent/app_strands.py
local.test:
	curl -X POST http://localhost:8080/invocations -H "Content-Type: application/json" -d '{"id_token": "${O_COGNITO_ID_TOKEN}", "prompt": "Get me a list of users that registered with this application."}'
