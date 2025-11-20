include etc/environment.sh

# api gateway
lambda: lambda.package lambda.deploy
lambda.package:
	sam package -t ${LAMBDA_TEMPLATE} --output-template-file ${LAMBDA_OUTPUT} --s3-bucket ${BUCKET} --s3-prefix ${LAMBDA_STACK}
lambda.deploy:
	sam deploy -t ${LAMBDA_OUTPUT} --region ${REGION} --stack-name ${LAMBDA_STACK} --parameter-overrides ${LAMBDA_PARAMS} --capabilities CAPABILITY_NAMED_IAM
lambda.delete:
	sam delete --stack-name ${LAMBDA_STACK}

# local agent
local.agent:
	npx tsx src/agent/agent.mts

# local testing
local.invoke:
	# sam build --profile ${PROFILE} --template ${LAMBDA_TEMPLATE} --parameter-overrides ${LAMBDA_PARAMS} --build-dir build --use-container
	sam local invoke -t ${LAMBDA_TEMPLATE} --parameter-overrides ${LAMBDA_PARAMS} --env-vars etc/envvars.json -e etc/event.json FnBuffered | jq

# lambda testing
lambda.invoke.sync:
	aws --profile ${PROFILE} lambda invoke --function-name ${O_FN} --invocation-type RequestResponse --payload file://etc/event.json --cli-binary-format raw-in-base64-out --log-type Tail tmp/fn.json | jq "." > tmp/response.json
	cat tmp/response.json | jq -r ".LogResult" | base64 --decode
	cat tmp/fn.json | jq
lambda.invoke.async:
	aws --profile ${PROFILE} lambda invoke --function-name ${O_FN} --invocation-type Event --payload file://etc/event.json --cli-binary-format raw-in-base64-out --log-type Tail tmp/fn.json | jq "."

# api testing
curl.buffered:
	curl -X POST -H "Content-Type: application/json" -d @etc/prompt.json ${O_API_ENDPOINT}/langgraph-buffered --no-buffer
curl.streaming:
	curl -X POST -H "Content-Type: application/json" -d @etc/prompt.json ${O_API_ENDPOINT}/langgraph-streaming --no-buffer