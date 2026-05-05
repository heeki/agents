"""Test script for the delegated-api time endpoint with OBO token."""
import argparse
import json
import sys

import httpx


def test_no_auth(endpoint: str, tz: str = "UTC"):
    url = f"{endpoint}/time"
    params = {"tz": tz} if tz else {}
    response = httpx.get(url, params=params)
    print(f"[NO AUTH] GET {url} ?tz={tz}")
    print(f"  Status: {response.status_code}")
    print(f"  Body:   {json.dumps(response.json(), indent=2)}")
    return response


def test_with_token(endpoint: str, token: str, tz: str = "UTC"):
    url = f"{endpoint}/time"
    params = {"tz": tz} if tz else {}
    headers = {"Authorization": f"Bearer {token}"}
    response = httpx.get(url, params=params, headers=headers)
    print(f"[AUTH] GET {url} ?tz={tz}")
    print(f"  Status: {response.status_code}")
    print(f"  Body:   {json.dumps(response.json(), indent=2)}")
    return response


def main():
    parser = argparse.ArgumentParser(description="Test delegated-api time endpoint")
    parser.add_argument("endpoint", help="API Gateway endpoint URL")
    parser.add_argument("--tz", default="America/New_York", help="Timezone (IANA format)")
    parser.add_argument("--token", help="Bearer token for authenticated request")
    parser.add_argument("--token-file", help="File containing bearer token")
    args = parser.parse_args()

    endpoint = args.endpoint.rstrip("/")

    print("=" * 60)
    print("Test 1: No authentication")
    print("=" * 60)
    test_no_auth(endpoint, args.tz)
    print()

    token = args.token
    if args.token_file:
        with open(args.token_file) as f:
            token = f.read().strip()

    if token:
        print("=" * 60)
        print("Test 2: With OBO token")
        print("=" * 60)
        test_with_token(endpoint, token, args.tz)
    else:
        print("Skipping authenticated test (no --token or --token-file provided)")


if __name__ == "__main__":
    main()
