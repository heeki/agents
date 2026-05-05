include etc/environment.sh

build:
	sam build \
		--profile $(PROFILE) \
		--template iac/template.yaml \
		--build-dir .aws-sam/build

deploy:
	sam deploy \
		--profile $(PROFILE) \
		--region $(REGION) \
		--template-file .aws-sam/build/template.yaml \
		--stack-name $(P_STACK) \
		--parameter-overrides \
			apiStage=$(P_API_STAGE) \
			fnMemory=$(P_FN_MEMORY) \
			fnTimeout=$(P_FN_TIMEOUT) \
			entraTenantId=$(P_ENTRA_TENANT_ID) \
			entraClientId=$(P_ENTRA_CLIENT_ID) \
			entraIssuer=$(P_ENTRA_ISSUER) \
			requiredScope=$(P_REQUIRED_SCOPE) \
		--capabilities CAPABILITY_NAMED_IAM \
		--resolve-s3 \
		--no-confirm-changeset

delete:
	sam delete \
		--profile $(PROFILE) \
		--region $(REGION) \
		--stack-name $(P_STACK) \
		--no-prompts

test.noauth:
	curl -s "$(O_API_ENDPOINT)/time?tz=America/New_York" | python3 -m json.tool

test.noauth.utc:
	curl -s "$(O_API_ENDPOINT)/time" | python3 -m json.tool

test.auth:
	python3 src/test_api.py $(O_API_ENDPOINT) --tz America/New_York

test.obo:
	P_ENTRA_TENANT_ID=$(P_ENTRA_TENANT_ID) \
	P_OBO_CLIENT_APP_CLIENT_ID=$(P_OBO_CLIENT_APP_CLIENT_ID) \
	P_OBO_CLIENT_APP_SECRET='$(P_OBO_CLIENT_APP_SECRET)' \
	P_OBO_MCP_APP_CLIENT_ID=$(P_OBO_MCP_APP_CLIENT_ID) \
	P_OBO_MCP_APP_SECRET='$(P_OBO_MCP_APP_SECRET)' \
	P_OBO_API_SCOPE=$(P_OBO_API_SCOPE) \
	python3 src/get_obo_token.py
