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

# Create a record from RECORD_CONFIG (default: etc/record.json), wait for ACTIVE, save to tmp/record.json
registry.record.create:
	uv run python src/main.py record.create | jq | tee tmp/record.json

# Create records for all files in tmp/records/, saving each output to tmp/outputs/<name>.json
registry.records.create:
	@mkdir -p tmp/outputs
	@for f in tmp/records/*.json; do \
		name=$$(basename $$f .json); \
		echo "=== $$f ===" >&2; \
		RECORD_CONFIG=$$f uv run python src/main.py record.create | jq | tee tmp/record.json tmp/outputs/$$name.json; \
	done

# Submit all records in tmp/outputs/ for approval
registry.records.submit:
	@for f in tmp/outputs/*.json; do \
		rid=$$(jq -r '.record_id' $$f); \
		echo "=== Submitting $$rid ($$(basename $$f .json)) ===" >&2; \
		uv run python src/main.py record.submit --record-id "$$rid" | jq; \
	done

# Approve all records in tmp/outputs/
registry.records.approve:
	@for f in tmp/outputs/*.json; do \
		rid=$$(jq -r '.record_id' $$f); \
		echo "=== Approving $$rid ($$(basename $$f .json)) ===" >&2; \
		uv run python src/main.py record.approve --record-id "$$rid" | jq; \
	done

# Get a specific record (reads record_id from tmp/record.json)
registry.record.get:
	@rid=$$(jq -r '.record_id // empty' tmp/record.json 2>/dev/null); \
	if [ -z "$$rid" ]; then echo "ERROR: tmp/record.json missing or has no record_id" >&2; exit 1; fi; \
	uv run python src/main.py record.get --record-id "$$rid" | jq

# Submit the record for approval
registry.record.submit:
	@rid=$$(jq -r '.record_id // empty' tmp/record.json 2>/dev/null); \
	if [ -z "$$rid" ]; then echo "ERROR: tmp/record.json missing or has no record_id" >&2; exit 1; fi; \
	uv run python src/main.py record.submit --record-id "$$rid" | jq

# Approve the record
registry.record.approve:
	@rid=$$(jq -r '.record_id // empty' tmp/record.json 2>/dev/null); \
	if [ -z "$$rid" ]; then echo "ERROR: tmp/record.json missing or has no record_id" >&2; exit 1; fi; \
	uv run python src/main.py record.approve --record-id "$$rid" | jq

# Reject the record
registry.record.reject:
	@rid=$$(jq -r '.record_id // empty' tmp/record.json 2>/dev/null); \
	if [ -z "$$rid" ]; then echo "ERROR: tmp/record.json missing or has no record_id" >&2; exit 1; fi; \
	uv run python src/main.py record.reject --record-id "$$rid" | jq

# List all records in the registry
registry.record.list:
	uv run python src/main.py record.list | jq

# Search approved records
registry.record.search:
	uv run python src/main.py record.search | jq

# Delete the record
registry.record.delete:
	@rid=$$(jq -r '.record_id // empty' tmp/record.json 2>/dev/null); \
	if [ -z "$$rid" ]; then echo "ERROR: tmp/record.json missing or has no record_id" >&2; exit 1; fi; \
	uv run python src/main.py record.delete --record-id "$$rid" | jq

# Delete all records in tmp/outputs/
registry.records.delete:
	@for f in tmp/outputs/*.json; do \
		rid=$$(jq -r '.record_id' $$f); \
		echo "=== Deleting $$rid ($$(basename $$f .json)) ===" >&2; \
		uv run python src/main.py record.delete --record-id "$$rid" | jq; \
	done

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
	rm -rf tmp/outputs
