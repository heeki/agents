include etc/environment.sh

# Sub-project 1: Interceptor Lambda
interceptor.build:
	sam build \
		--profile $(PROFILE) \
		--template interceptor/iac/interceptor.yaml \
		--build-dir interceptor/.aws-sam/build

interceptor.deploy:
	sam deploy \
		--profile $(PROFILE) \
		--region $(REGION) \
		--template-file interceptor/.aws-sam/build/template.yaml \
		--stack-name $(P_STACK_INTERCEPTOR) \
		--parameter-overrides \
			pFunctionName=$(P_INTERCEPTOR_FUNCTION_NAME) \
			pAccountId=$(ACCOUNTID) \
		--capabilities CAPABILITY_NAMED_IAM \
		--resolve-s3 \
		--no-confirm-changeset

interceptor.delete:
	sam delete \
		--profile $(PROFILE) \
		--region $(REGION) \
		--stack-name $(P_STACK_INTERCEPTOR) \
		--no-prompts

interceptor.local.tools_call:
	sam local invoke InterceptorFunction \
		--profile $(PROFILE) \
		--template interceptor/iac/interceptor.yaml \
		--event interceptor/events/test_tools_call.json

interceptor.local.tools_list:
	sam local invoke InterceptorFunction \
		--profile $(PROFILE) \
		--template interceptor/iac/interceptor.yaml \
		--event interceptor/events/test_tools_list.json

# Sub-project 2, Phase 1: MCP Server on AgentCore Runtime
runtime.package:
	rm -rf tmp/runtime_package tmp/runtime_*.zip
	uv pip install \
		--python-platform aarch64-manylinux2014 \
		--python-version 3.12 \
		--target tmp/runtime_package \
		--only-binary :all: \
		-r app/mcpserver/requirements.txt
	cp app/mcpserver/main.py tmp/runtime_package/
	cd tmp/runtime_package && zip -qr ../runtime_tmp.zip .
	P_ZIP_MD5=$$(md5 -q tmp/runtime_tmp.zip) && \
	mv tmp/runtime_tmp.zip tmp/runtime_$${P_ZIP_MD5}.zip && \
	aws s3 cp \
		tmp/runtime_$${P_ZIP_MD5}.zip \
		s3://$(P_S3_BUCKET)/$(P_STACK_RUNTIME)/runtime_$${P_ZIP_MD5}.zip \
		--profile $(PROFILE) \
		--region $(REGION)

runtime.deploy:
	$(eval P_ZIP_NAME=$(shell ls -t tmp/runtime_*.zip 2>/dev/null | head -1 | xargs basename))
	sam deploy \
		--profile $(PROFILE) \
		--region $(REGION) \
		--template-file app/mcpserver/iac/runtime.yaml \
		--stack-name $(P_STACK_RUNTIME) \
		--parameter-overrides \
			pRuntimeName=$(P_RUNTIME_NAME) \
			pAccountId=$(ACCOUNTID) \
			pRegion=$(REGION) \
			pS3Bucket=$(P_S3_BUCKET) \
			pS3Prefix=$(P_STACK_RUNTIME)/$(P_ZIP_NAME) \
			pCognitoIssuer=$(O_COGNITO_ISSUER) \
			pCognitoAudience=$(O_COGNITO_CLIENT_ID) \
		--capabilities CAPABILITY_NAMED_IAM \
		--no-confirm-changeset

runtime.delete:
	sam delete \
		--profile $(PROFILE) \
		--region $(REGION) \
		--stack-name $(P_STACK_RUNTIME) \
		--no-prompts

runtime.invoke:
	python3 app/mcpserver/test_runtime.py $(O_RUNTIME_ARN) --region $(REGION) \
		--jwt \
		--cognito-domain $(P_COGNITO_DOMAIN) \
		--cognito-user-pool-id $(O_COGNITO_USER_POOL_ID) \
		--cognito-client-id $(O_COGNITO_CLIENT_ID) \
		--scope "https://$(P_GATEWAY_NAME).agentcore.local/invoke"

runtime.observability:
	python3 app/mcpserver/setup_observability.py \
		--action create \
		--region $(REGION) \
		--runtime-arn $(O_RUNTIME_ARN) \
		--runtime-id $(O_RUNTIME_ID) \
		--account-id $(ACCOUNTID)

runtime.observability.delete:
	python3 app/mcpserver/setup_observability.py \
		--action delete \
		--region $(REGION) \
		--runtime-id $(O_RUNTIME_ID)

runtime.observability.get:
	python3 app/mcpserver/setup_observability.py \
		--action get \
		--region $(REGION) \
		--runtime-id $(O_RUNTIME_ID)

runtime.logs:
	aws logs tail \
		"/aws/vendedlogs/bedrock-agentcore/runtime/APPLICATION_LOGS/$(O_RUNTIME_ID)" \
		--since 5m \
		--profile $(PROFILE) \
		--region $(REGION)

runtime.status:
	python3 -c "\
	import boto3, json; \
	client = boto3.client('bedrock-agentcore-control', region_name='$(REGION)'); \
	response = client.get_agent_runtime(agentRuntimeId='$(O_RUNTIME_ID)'); \
	response.pop('ResponseMetadata', None); \
	print(json.dumps(response, indent=2, default=str))"

# Sub-project 2, Phase 2: AgentCore Gateway
gateway.deploy:
	sam deploy \
		--profile $(PROFILE) \
		--region $(REGION) \
		--template-file gateway/iac/gateway.yaml \
		--stack-name $(P_STACK_GATEWAY) \
		--parameter-overrides \
			pGatewayName=$(P_GATEWAY_NAME) \
			pAccountId=$(ACCOUNTID) \
			pRegion=$(REGION) \
			pRuntimeArn=$(O_RUNTIME_ARN) \
			pRuntimeId=$(O_RUNTIME_ID) \
			pCredentialProviderArn=$(O_CREDENTIAL_PROVIDER_ARN) \
			pCognitoDomain=$(P_COGNITO_DOMAIN) \
			pInterceptorArn=$(O_INTERCEPTOR_ARN) \
		--capabilities CAPABILITY_NAMED_IAM \
		--no-confirm-changeset

gateway.setup:
	python3 gateway/setup_oauth.py \
		--action create \
		--region $(REGION) \
		--name $(P_OAUTH_PROVIDER_NAME) \
		--cognito-discovery-url $(O_COGNITO_DISCOVERY_URL) \
		--cognito-user-pool-id $(O_COGNITO_USER_POOL_ID) \
		--cognito-client-id $(O_COGNITO_CLIENT_ID)

gateway.setup.delete:
	python3 gateway/setup_oauth.py \
		--action delete \
		--region $(REGION) \
		--name $(P_OAUTH_PROVIDER_NAME)

gateway.setup.get:
	python3 gateway/setup_oauth.py \
		--action get \
		--region $(REGION) \
		--name $(P_OAUTH_PROVIDER_NAME)

gateway.delete:
	sam delete \
		--profile $(PROFILE) \
		--region $(REGION) \
		--stack-name $(P_STACK_GATEWAY) \
		--no-prompts

gateway.invoke:
	python3 gateway/test_gateway.py $(O_GATEWAY_URL)

gateway.status:
	python3 -c "\
	import boto3, json; \
	client = boto3.client('bedrock-agentcore-control', region_name='$(REGION)'); \
	response = client.get_gateway(gatewayIdentifier='$(O_GATEWAY_ID)'); \
	response.pop('ResponseMetadata', None); \
	print(json.dumps(response, indent=2, default=str))"
