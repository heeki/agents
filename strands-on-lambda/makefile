include etc/environment.sh

# dependencies
layer: layer.build layer.package layer.deploy
layer.build:
	sam build -t ${LAYER_TEMPLATE} --parameter-overrides ${LAYER_PARAMS} --build-dir build --manifest ./requirements.txt --use-container
layer.package:
	sam package -t build/template.yaml --region ${REGION} --output-template-file ${LAYER_OUTPUT} --s3-bucket ${BUCKET} --s3-prefix ${LAYER_STACK}
layer.deploy:
	sam deploy -t ${LAYER_OUTPUT} --region ${REGION} --stack-name ${LAYER_STACK} --parameter-overrides ${LAYER_PARAMS} --capabilities CAPABILITY_NAMED_IAM

# api gateway
lambda: lambda.package lambda.deploy
lambda.package:
	sam package -t ${LAMBDA_TEMPLATE} --output-template-file ${LAMBDA_OUTPUT} --s3-bucket ${BUCKET} --s3-prefix ${LAMBDA_STACK}
lambda.deploy:
	sam deploy -t ${LAMBDA_OUTPUT} --region ${REGION} --stack-name ${LAMBDA_STACK} --parameter-overrides ${LAMBDA_PARAMS} --capabilities CAPABILITY_NAMED_IAM
lambda.delete:
	sam delete --stack-name ${LAMBDA_STACK}

# local testing
sam.local.api:
	sam local start-api -t ${LAMBDA_TEMPLATE} --parameter-overrides ${LAMBDA_PARAMS} --env-vars etc/envvars.json
sam.local.api.build:
	sam build --profile ${PROFILE} --template ${LAMBDA_TEMPLATE} --parameter-overrides ${LAMBDA_PARAMS} --build-dir build --manifest requirements.txt --use-container
	sam local start-api -t build/template.yaml --parameter-overrides ${LAMBDA_PARAMS} --env-vars etc/envvars.json
sam.local.invoke:
	sam local invoke -t ${LAMBDA_TEMPLATE} --parameter-overrides ${LAMBDA_PARAMS} --env-vars etc/envvars.json -e etc/event.json Fn | jq

# lambda testing
lambda.invoke.sync:
	aws --profile ${PROFILE} lambda invoke --function-name ${O_FN} --invocation-type RequestResponse --payload file://etc/event.json --cli-binary-format raw-in-base64-out --log-type Tail tmp/fn.json | jq "." > tmp/response.json
	cat tmp/response.json | jq -r ".LogResult" | base64 --decode
	cat tmp/fn.json | jq
lambda.invoke.async:
	aws --profile ${PROFILE} lambda invoke --function-name ${O_FN} --invocation-type Event --payload file://etc/event.json --cli-binary-format raw-in-base64-out --log-type Tail tmp/fn.json | jq "."

# api testing
curl.post.sync:
	curl -X POST -H "Content-Type: application/json" -d @etc/prompt.json ${O_API_ENDPOINT}/strands --no-buffer
curl.post.stream:
	curl -X POST -H "Content-Type: application/json" -d @etc/prompt.json ${O_API_ENDPOINT}/strands-streaming --no-buffer