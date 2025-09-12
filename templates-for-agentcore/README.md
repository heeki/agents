# Templates for AgentCore

This repository contains deployment templates for Amazon Bedrock AgentCore with API Gateway integration, supporting both Cognito JWT and custom API key authorization patterns.

## Project Structure

```
agents/
├── README.md
└── templates-for-agentcore/
    ├── agent/
    │   └── app_strands.py                    # Strands Agent entrypoint
    ├── etc/
    │   └── environment.sh                    # Environment configuration
    ├── iac/                                  # Infrastructure as Code
    │   ├── apigw.yaml                        # API Gateway with Lambda functions
    │   ├── cognito.yaml                      # Cognito user pool configuration
    │   ├── infrastructure.yaml               # ACM certificate, API Gateway domain, ECR repository, and IAM roles
    │   ├── openapi.yaml                      # OpenAPI specification for API Gateway
    │   ├── deploy_runtime.py                 # AgentCore Runtime deployment helper
    │   ├── deploy_gateway.py                 # AgentCore Gateway deployment helper
    │   └── generate_secrethash.py            # Cognito secret hash generator
    ├── src/
    │   ├── api-gateway/
    │   │   └── fn.py                         # Lambda function for API Gateway backend integration
    │   ├── authorizer/
    │   │   └── fn.py                         # Lambda function for API Gateway custom authorizer
    │   └── agentcore-gateway/
    │       └── fn.py                         # Lambda function for AgentCore Gateway integration
    ├── dockerfile.strands                    # Strands Agent container
    ├── pyproject.toml
    └── requirements.txt
```

## Prerequisites

- Python 3.12+
- AWS CLI configured with a profile that has access to Bedrock AgentCore, Cognito, CloudFormation, ECR, API Gateway, Lambda
- SAM CLI for local testing
- jq for JSON processing

## Deployment Options

This template supports two authorization patterns:

### 1) Cognito JWT Authorization

Uses Amazon Cognito User Pool for JWT token validation with API Gateway.

### 2) Custom API Key Authorization

Uses a custom Lambda authorizer for simple token-based authentication.

## Quick Start

1. **Initialize environment**
   ```bash
   cd templates-for-agentcore
   uv pip install -r requirements.txt
   cp etc/environment.template.strands etc/environment.sh
   # edit etc/environment.sh with your values
   ```

2. **Deploy infrastructure resources**
   ```bash
   make infrastructure
   # update outputs for O_ECR_REPO, O_ECR_REPO_ARN, O_ECR_REPO_URI, O_AGENT_ROLE
   ```

3. **Deploy Cognito (for JWT auth)**
   ```bash
   make cognito
   # update outputs for O_COGNITO_USERPOOL, O_COGNITO_CLIENTID, etc.
   ```

4. **Set up Cognito user**
   ```bash
   # Generate secret hash
   make cognito.secrethash
   # copy SECRETHASH output to P_COGNITO_SECRETHASH in etc/environment.sh

   # Set up user (check email for temp password)
   make cognito.admin
   make cognito.updatepw
   ```

5. **Deploy API Gateway**
   ```bash
   make apigw
   ```

6. **Test the API**
   ```bash
   # test without auth (should return 401)
   make curl.apigw

   # test with Cognito JWT
   make cognito.login
   make curl.apigw.cognito

   # test with API key auth
   make curl.apigw.apikey
   ```

## Configuration

Key environment variables in `etc/environment.sh`:

### AWS Configuration
- `PROFILE`, `REGION`, `BUCKET`, `ACCOUNTID`

### API Gateway
- `O_API_ENDPOINT` - Deployed API Gateway endpoint
- `O_FN_API` - Main Lambda function name
- `O_FN_AUTH` - Authorizer Lambda function name

### Cognito (JWT Auth)
- `P_COGNITO_*` - User pool parameters
- `O_COGNITO_*` - User pool outputs
- `P_COGNITO_SECRETHASH` - Secret hash for client

### AgentCore Gateway
- `GATEWAY_NAME`, `GATEWAY_DESCRIPTION` - Gateway configuration
- `TARGET_NAME`, `TARGET_DESCRIPTION` - Target configuration
- `OPENAPI_FILE` - OpenAPI specification file

## Make Targets

### Infrastructure
- `make infrastructure` - Deploy ECR repository and IAM roles
- `make cognito` - Deploy Cognito user pool and client
- `make apigw` - Deploy API Gateway with Lambda functions

### Cognito Management
- `make cognito.secrethash` - Generate secret hash for client
- `make cognito.admin` - Admin authentication
- `make cognito.updatepw` - Update user password
- `make cognito.login` - User login and token generation
- `make cognito.client_credentials` - OAuth2 client credentials flow

### API Testing
- `make curl.apigw` - Test API without authorization
- `make curl.apigw.cognito` - Test API with Cognito JWT
- `make curl.apigw.apikey` - Test API with API key auth

### Local Development
- `make sam.local.api` - Run API Gateway locally
- `make sam.local.invoke` - Invoke Lambda function locally
- `make local.agent` - Run Strands agent locally

### AgentCore Gateway
- `make agentcore.gateway.create` - Create AgentCore gateway
- `make agentcore.gateway.update` - Update AgentCore gateway
- `make agentcore.target.create` - Create gateway target
- `make agentcore.target.update` - Update gateway target

## Authorization Patterns

### Cognito JWT Authorization

The API Gateway uses Cognito User Pool authorizer for JWT validation:

```yaml
securitySchemes:
  cognito-authorizer:
    type: apiKey
    name: Authorization
    in: header
    x-amazon-apigateway-authtype: cognito_user_pools
    x-amazon-apigateway-authorizer:
      type: cognito_user_pools
      providerARNs:
        - Fn::Sub: "arn:aws:cognito-idp:${AWS::Region}:${AWS::AccountId}:userpool/${cognitoUserPoolId}"
```

### Custom API Key Authorization

Uses a Lambda authorizer for simple token validation:

```yaml
securitySchemes:
  api-key-authorizer:
    type: apiKey
    name: Authorization
    in: header
    x-amazon-apigateway-authtype: custom
    x-amazon-apigateway-authorizer:
      type: request
      authorizerUri: !Sub 'arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${FnAuth.Arn}/invocations'
```

## Troubleshooting

### Common Issues

1. **401 Unauthorized with Cognito**
   - Ensure you're using the ID token, not access token
   - Check that the user pool is properly configured
   - Verify the JWT token hasn't expired

2. **500 AuthorizerConfigurationException**
   - Check Lambda authorizer function logs
   - Verify authorizer permissions
   - Ensure authorizer type is correct (`token` vs `request`)

3. **OpenAPI Validation Errors**
   - Ensure all operations have `operationId`
   - Check that `servers` property is configured
   - Verify security schemes are properly defined

### Debugging Steps

1. Check API Gateway access logs for authorization details
2. Review Lambda function logs in CloudWatch
3. Test authorizer function directly with `sam local invoke`
4. Verify Cognito token claims and expiration

## Notes

- Increment `C_VERSION` for each new container image
- The custom authorizer expects `Authorization: allow` or `Authorization: deny`
- OpenAPI specification requires `operationId` for all operations
