include etc/environment.sh

# ============================================================================
# SETUP
# ============================================================================
setup:
	uv venv && uv pip install -r requirements.txt

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

# Acquire an M2M access token via client_credentials and save to tmp/
cognito.token:
	@curl -s -X POST "${O_COGNITO_DOMAIN}/oauth2/token" \
		-H "Content-Type: application/x-www-form-urlencoded" \
		-u "${O_COGNITO_M2M_CLIENTID}:${O_COGNITO_M2M_CLIENTSECRET}" \
		-d "grant_type=client_credentials&scope=${O_COGNITO_SCOPE}" | jq | tee tmp/cognito_token.json

# ============================================================================
# REGISTRY — TOKEN (via well-known OIDC discovery)
# ============================================================================
# Uses COGNITO_WELLKNOWN_URL to discover the token endpoint, then performs
# the client_credentials grant.
registry.token:
	uv run python src/main.py token | jq | tee tmp/registry_token.json

# ============================================================================
# REGISTRY — REGISTRIES
# ============================================================================
registry.list:
	uv run python src/main.py registry.list | jq

# ============================================================================
# REGISTRY — RECORDS
# ============================================================================

# Create a record from etc/record.json, wait for ACTIVE, save to tmp/record.json
registry.record.create:
	uv run python src/main.py record.create | jq | tee tmp/record.json

# Get a specific record (reads record_id from tmp/record.json)
registry.record.get:
	uv run python src/main.py record.get \
		--record-id "$$(jq -r '.record_id' tmp/record.json)" | jq

# Submit the record for approval
registry.record.submit:
	uv run python src/main.py record.submit \
		--record-id "$$(jq -r '.record_id' tmp/record.json)" | jq

# Approve the record
registry.record.approve:
	uv run python src/main.py record.approve \
		--record-id "$$(jq -r '.record_id' tmp/record.json)" | jq

# Reject the record
registry.record.reject:
	uv run python src/main.py record.reject \
		--record-id "$$(jq -r '.record_id' tmp/record.json)" | jq

# List all records in the registry
registry.record.list:
	uv run python src/main.py record.list | jq

# Search approved records
registry.record.search:
	uv run python src/main.py record.search | jq

# Delete the record
registry.record.delete:
	uv run python src/main.py record.delete \
		--record-id "$$(jq -r '.record_id' tmp/record.json)" | jq

# ============================================================================
# REGISTRY — FULL WORKFLOW
# Runs all steps end-to-end: auth → create → submit → approve → list → search
# ============================================================================
registry.workflow:
	uv run python src/main.py workflow | jq | tee tmp/workflow.json

# ============================================================================
# CLEANUP
# ============================================================================
clean:
	rm -rf .venv
	rm -rf iac/*_output.yaml
	rm -f tmp/record.json tmp/registry_token.json tmp/cognito_token.json tmp/workflow.json
