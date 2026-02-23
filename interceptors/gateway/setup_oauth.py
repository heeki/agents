import argparse
import boto3
import json
import sys


def get_cognito_client_secret(region: str, user_pool_id: str, client_id: str) -> str:
    """Retrieve Cognito app client secret via describe_user_pool_client."""
    client = boto3.client("cognito-idp", region_name=region)
    response = client.describe_user_pool_client(
        UserPoolId=user_pool_id,
        ClientId=client_id,
    )
    secret = response["UserPoolClient"].get("ClientSecret", "")
    if not secret:
        print("Error: Cognito app client has no secret", file=sys.stderr)
        sys.exit(1)
    return secret


def create_credential_provider(
    region: str,
    name: str,
    discovery_url: str,
    client_id: str,
    client_secret: str,
) -> dict:
    """Create an OAuth2 Credential Provider in AgentCore Identity."""
    client = boto3.client("bedrock-agentcore-control", region_name=region)
    response = client.create_oauth2_credential_provider(
        name=name,
        credentialProviderVendor="CustomOauth2",
        oauth2ProviderConfigInput={
            "customOauth2ProviderConfig": {
                "oauthDiscovery": {
                    "discoveryUrl": discovery_url,
                },
                "clientId": client_id,
                "clientSecret": client_secret,
            },
        },
    )
    response.pop("ResponseMetadata", None)
    return response


def delete_credential_provider(region: str, name: str) -> dict:
    """Delete an OAuth2 Credential Provider."""
    client = boto3.client("bedrock-agentcore-control", region_name=region)
    response = client.delete_oauth2_credential_provider(name=name)
    response.pop("ResponseMetadata", None)
    return response


def get_credential_provider(region: str, name: str) -> dict:
    """Get an OAuth2 Credential Provider."""
    client = boto3.client("bedrock-agentcore-control", region_name=region)
    response = client.get_oauth2_credential_provider(name=name)
    response.pop("ResponseMetadata", None)
    return response


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage OAuth2 Credential Provider for AgentCore Gateway")
    parser.add_argument("--action", choices=["create", "delete", "get", "get-secret"], required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--name", default="interceptors-demo-oauth-provider")
    parser.add_argument("--cognito-discovery-url", default="")
    parser.add_argument("--cognito-user-pool-id", default="")
    parser.add_argument("--cognito-client-id", default="")
    args = parser.parse_args()

    if args.action == "get-secret":
        secret = get_cognito_client_secret(args.region, args.cognito_user_pool_id, args.cognito_client_id)
        print(secret)
    elif args.action == "create":
        secret = get_cognito_client_secret(args.region, args.cognito_user_pool_id, args.cognito_client_id)
        result = create_credential_provider(
            region=args.region,
            name=args.name,
            discovery_url=args.cognito_discovery_url,
            client_id=args.cognito_client_id,
            client_secret=secret,
        )
        print(json.dumps(result, indent=2, default=str))
    elif args.action == "delete":
        result = delete_credential_provider(args.region, args.name)
        print(json.dumps(result, indent=2, default=str))
    elif args.action == "get":
        result = get_credential_provider(args.region, args.name)
        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
