import boto3
import json
import random

# initialization
session = boto3.session.Session()
client = session.client('bedrock-agentcore')

# helper functions
def build_response(code, body):
    headers = {
        "Content-Type": "application/json"
    }
    response = {
        "isBase64Encoded": False,
        "statusCode": code,
        "headers": headers,
        "body": body
    }
    return response

def handler(event, context):
    output = build_response(200, json.dumps(event))
    users = [
        {
            "name": f"user@{i}",
            "email": f"user.{i}@example.com"
        } for i in [random.randint(100, 999) for _ in range(5)]
    ]
    output = build_response(200, json.dumps(users))
    print(json.dumps(output))
    return output
