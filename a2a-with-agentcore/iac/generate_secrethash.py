#!/usr/bin/env python3
"""Generate Cognito secret hash for authentication.

Usage:
    python generate_secrethash.py <username> <client_id> <client_secret>
"""

import base64
import hashlib
import hmac
import sys


def generate_secret_hash(username: str, client_id: str, client_secret: str) -> str:
    """Generate the Cognito secret hash.

    Args:
        username: The Cognito username.
        client_id: The Cognito app client ID.
        client_secret: The Cognito app client secret.

    Returns:
        Base64-encoded HMAC-SHA256 hash.
    """
    message = username + client_id
    dig = hmac.new(
        client_secret.encode("utf-8"),
        message.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    return base64.b64encode(dig).decode()


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python generate_secrethash.py <username> <client_id> <client_secret>")
        sys.exit(1)

    username = sys.argv[1]
    client_id = sys.argv[2]
    client_secret = sys.argv[3]

    secret_hash = generate_secret_hash(username, client_id, client_secret)
    print(secret_hash)
