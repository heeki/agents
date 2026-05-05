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


def _build_provider_config(
    discovery_url: str,
    client_id: str,
    client_secret: str,
    obo_grant_type: str = "",
) -> dict:
    """Build the customOauth2ProviderConfig dict."""
    config: dict = {
        "oauthDiscovery": {
            "discoveryUrl": discovery_url,
        },
        "clientId": client_id,
        "clientSecret": client_secret,
    }
    if obo_grant_type:
        obo_config: dict = {
            "grantType": obo_grant_type,
        }
        if obo_grant_type == "TOKEN_EXCHANGE":
            obo_config["tokenExchangeGrantTypeConfig"] = {
                "actorTokenContent": "M2M",
            }
        config["onBehalfOfTokenExchangeConfig"] = obo_config
        if obo_grant_type == "JWT_AUTHORIZATION_GRANT":
            config["clientAuthenticationMethod"] = "CLIENT_SECRET_POST"
    return config


def ensure_workload_identity(region: str, name: str) -> None:
    """Create a workload identity with the same name as the credential provider if it doesn't exist."""
    client = boto3.client("bedrock-agentcore-control", region_name=region)
    try:
        client.get_workload_identity(name=name)
    except client.exceptions.ResourceNotFoundException:
        print(f"Creating workload identity '{name}'...", file=sys.stderr)
        client.create_workload_identity(name=name)
    except Exception:
        pass


def create_credential_provider(
    region: str,
    name: str,
    discovery_url: str,
    client_id: str,
    client_secret: str,
    obo_grant_type: str = "",
) -> dict:
    """Create an OAuth2 Credential Provider in AgentCore Identity.
    If it already exists, updates it instead.
    Also ensures a matching workload identity exists for OBO flows."""
    client = boto3.client("bedrock-agentcore-control", region_name=region)
    config = _build_provider_config(discovery_url, client_id, client_secret, obo_grant_type)
    try:
        response = client.create_oauth2_credential_provider(
            name=name,
            credentialProviderVendor="CustomOauth2",
            oauth2ProviderConfigInput={
                "customOauth2ProviderConfig": config,
            },
        )
    except client.exceptions.ConflictException:
        print(f"Credential provider '{name}' already exists, updating...", file=sys.stderr)
        response = client.update_oauth2_credential_provider(
            name=name,
            credentialProviderVendor="CustomOauth2",
            oauth2ProviderConfigInput={
                "customOauth2ProviderConfig": config,
            },
        )
    if obo_grant_type:
        ensure_workload_identity(region, name)
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
    parser.add_argument("--client-secret", default="", help="Client secret (for non-Cognito IdPs like Entra ID)")
    parser.add_argument("--obo-grant-type", default="", choices=["", "TOKEN_EXCHANGE", "JWT_AUTHORIZATION_GRANT"],
                        help="OBO grant type for on-behalf-of token exchange")
    args = parser.parse_args()

    if args.action == "get-secret":
        secret = get_cognito_client_secret(args.region, args.cognito_user_pool_id, args.cognito_client_id)
        print(secret)
    elif args.action == "create":
        if args.client_secret:
            secret = args.client_secret
        else:
            secret = get_cognito_client_secret(args.region, args.cognito_user_pool_id, args.cognito_client_id)
        result = create_credential_provider(
            region=args.region,
            name=args.name,
            discovery_url=args.cognito_discovery_url,
            client_id=args.cognito_client_id,
            client_secret=secret,
            obo_grant_type=args.obo_grant_type,
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
