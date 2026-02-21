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
