"""
Acquire an OBO token for testing. Two-step flow:
1. Get a user token from the client app (client_credentials)
2. Exchange it for an OBO token via the MCP server app
3. The OBO token targets the API with time:read scope

Configuration is read from environment variables (source etc/environment.sh).
"""
import argparse
import json
import os
import sys

import httpx

TENANT_ID = os.environ.get("P_ENTRA_TENANT_ID", "")
TOKEN_URL = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"

CLIENT_APP_CLIENT_ID = os.environ.get("P_OBO_CLIENT_APP_CLIENT_ID", "")
CLIENT_APP_SECRET = os.environ.get("P_OBO_CLIENT_APP_SECRET", "")
MCP_APP_CLIENT_ID = os.environ.get("P_OBO_MCP_APP_CLIENT_ID", "")
MCP_APP_SECRET = os.environ.get("P_OBO_MCP_APP_SECRET", "")
API_SCOPE = os.environ.get("P_OBO_API_SCOPE", "")


def get_client_token() -> str:
    """Get a token from the client app targeting the MCP server's OBO scope."""
    data = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_APP_CLIENT_ID,
        "client_secret": CLIENT_APP_SECRET,
        "scope": f"api://{MCP_APP_CLIENT_ID}/.default",
    }
    response = httpx.post(TOKEN_URL, data=data)
    if response.status_code != 200:
        print(f"Failed to get client token: {response.status_code}")
        print(response.text)
        sys.exit(1)
    token_data = response.json()
    return token_data["access_token"]


def get_obo_token(assertion: str) -> str:
    """Exchange the client token for an OBO token targeting the time API."""
    data = {
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "client_id": MCP_APP_CLIENT_ID,
        "client_secret": MCP_APP_SECRET,
        "assertion": assertion,
        "scope": API_SCOPE,
        "requested_token_use": "on_behalf_of",
    }
    response = httpx.post(TOKEN_URL, data=data)
    if response.status_code != 200:
        print(f"Failed to get OBO token: {response.status_code}")
        print(response.text)
        sys.exit(1)
    token_data = response.json()
    return token_data["access_token"]


def main():
    parser = argparse.ArgumentParser(description="Get OBO token for delegated-api testing")
    parser.add_argument("--client-token", help="Pre-acquired client token (skip step 1)")
    parser.add_argument("--output", choices=["token", "full"], default="token")
    args = parser.parse_args()

    missing = [v for v in ("P_ENTRA_TENANT_ID", "P_OBO_CLIENT_APP_CLIENT_ID", "P_OBO_CLIENT_APP_SECRET",
                           "P_OBO_MCP_APP_CLIENT_ID", "P_OBO_MCP_APP_SECRET", "P_OBO_API_SCOPE")
               if not os.environ.get(v)]
    if missing:
        print(f"Missing environment variables: {', '.join(missing)}", file=sys.stderr)
        print("Source etc/environment.sh first: export $(grep -v '^#' etc/environment.sh | xargs)", file=sys.stderr)
        sys.exit(1)

    if args.client_token:
        client_token = args.client_token
    else:
        print("Step 1: Acquiring client token (client_credentials)...")
        client_token = get_client_token()
        print(f"  Got client token ({len(client_token)} chars)")

    print("Step 2: Exchanging for OBO token...")
    obo_token = get_obo_token(client_token)
    print(f"  Got OBO token ({len(obo_token)} chars)")
    if args.output == "full":
        print(json.dumps({"client_token": client_token, "obo_token": obo_token}, indent=2))
    else:
        print(obo_token)


if __name__ == "__main__":
    main()
