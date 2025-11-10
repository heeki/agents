import json
import os

def extract_token(event):
    if "Authorization" in event["headers"]:
        token = event["headers"]["Authorization"]
    elif "authorization" in event["headers"]:
        token = event["headers"]["authorization"]
    else:
        token = "deny"
    return token

def extract_user(event):
    if "requestContext" in event and "identity" in event["requestContext"] and "user" in event["requestContext"]["identity"]:
        if event["requestContext"]["identity"]["user"] is not None:
            user = event["requestContext"]["identity"]["user"]
        else:
            user = "unidentified_user"
    else:
        user = "invalid_request"
    return user

def extract_method_context(event):
    if "methodArn" in event:
        resource = event["methodArn"]
        payload_version = "1.0"
        is_simple = "false"
    elif "routeArn" in event:
        resource = "{}/*".format(event["routeArn"])
        payload_version = event["version"]
        is_simple = os.environ.get("SET_SIMPLE", "false")
    context = {
        "pversion": payload_version,
        "simple": is_simple,
    }
    return resource, context

def generate_policy(principal, effect, resource, context):
    response = {
        "principalId": principal,
        "context": context
    }
    if effect and resource:
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": effect,
                    "Action": "execute-api:Invoke",
                    "Resource": [resource]
                }
            ]
        }
        response["policyDocument"] = policy
    return response

def handler(event, context):
    print(json.dumps(event))
    token = extract_token(event)
    user = extract_user(event)
    resource, context = extract_method_context(event)
    # WARNING: using an insecure token for demo purposes, do not use for production purposes
    if token == "allow":
        response = generate_policy(user, "Allow", resource, context)
    elif token == "deny":
        response = generate_policy(user, "Deny", resource, context)
    else:
        raise Exception("invalid_request")
    print(json.dumps(response))
    return response

