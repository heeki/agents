"""Manage CloudWatch Logs vended delivery for AgentCore Runtime observability.

CloudWatch Logs delivery pipelines are API-managed resources (no CFN support).
This script creates/deletes the delivery source, destination, and delivery
that forward structured OTEL application logs from the runtime to CloudWatch.
"""
import argparse
import json
import sys

import boto3


def create_delivery(logs_client: boto3.client, runtime_arn: str, runtime_id: str, account_id: str, region: str) -> None:
    log_group_name = f"/aws/vendedlogs/bedrock-agentcore/runtime/APPLICATION_LOGS/{runtime_id}"
    log_group_arn = f"arn:aws:logs:{region}:{account_id}:log-group:{log_group_name}"
    source_name = f"{runtime_id}-logs-source"
    dest_name = f"{runtime_id}-logs-destination"

    # Create log group
    try:
        logs_client.create_log_group(logGroupName=log_group_name)
        print(f"Created log group: {log_group_name}")
    except logs_client.exceptions.ResourceAlreadyExistsException:
        print(f"Log group already exists: {log_group_name}")

    # Create delivery source
    resp = logs_client.put_delivery_source(
        name=source_name,
        logType="APPLICATION_LOGS",
        resourceArn=runtime_arn,
    )
    print(f"Created delivery source: {source_name}")

    # Create delivery destination
    resp = logs_client.put_delivery_destination(
        name=dest_name,
        deliveryDestinationType="CWL",
        deliveryDestinationConfiguration={
            "destinationResourceArn": log_group_arn,
        },
    )
    dest_arn = resp["deliveryDestination"]["arn"]
    print(f"Created delivery destination: {dest_name}")

    # Create delivery
    resp = logs_client.create_delivery(
        deliverySourceName=source_name,
        deliveryDestinationArn=dest_arn,
    )
    delivery_id = resp["delivery"]["id"]
    print(f"Created delivery: {delivery_id}")
    print(f"Log group: {log_group_name}")


def delete_delivery(logs_client: boto3.client, runtime_id: str) -> None:
    source_name = f"{runtime_id}-logs-source"
    dest_name = f"{runtime_id}-logs-destination"
    log_group_name = f"/aws/vendedlogs/bedrock-agentcore/runtime/APPLICATION_LOGS/{runtime_id}"

    # Find and delete deliveries for this source
    try:
        deliveries = logs_client.describe_deliveries()
        for d in deliveries.get("deliveries", []):
            if d.get("deliverySourceName") == source_name:
                logs_client.delete_delivery(id=d["id"])
                print(f"Deleted delivery: {d['id']}")
    except Exception as e:
        print(f"Warning deleting deliveries: {e}")

    # Delete destination
    try:
        logs_client.delete_delivery_destination(name=dest_name)
        print(f"Deleted delivery destination: {dest_name}")
    except Exception as e:
        print(f"Warning deleting destination: {e}")

    # Delete source
    try:
        logs_client.delete_delivery_source(name=source_name)
        print(f"Deleted delivery source: {source_name}")
    except Exception as e:
        print(f"Warning deleting source: {e}")

    # Delete log group
    try:
        logs_client.delete_log_group(logGroupName=log_group_name)
        print(f"Deleted log group: {log_group_name}")
    except Exception as e:
        print(f"Warning deleting log group: {e}")


def get_delivery(logs_client: boto3.client, runtime_id: str) -> None:
    source_name = f"{runtime_id}-logs-source"
    log_group_name = f"/aws/vendedlogs/bedrock-agentcore/runtime/APPLICATION_LOGS/{runtime_id}"

    try:
        sources = logs_client.describe_delivery_sources()
        for src in sources.get("deliverySources", []):
            if src["name"] == source_name:
                print("Delivery source:")
                print(json.dumps(src, indent=2, default=str))
                break
        else:
            print(f"No delivery source found: {source_name}")
            return
    except Exception as e:
        print(f"Error: {e}")
        return

    deliveries = logs_client.describe_deliveries()
    for d in deliveries.get("deliveries", []):
        if d.get("deliverySourceName") == source_name:
            print("\nDelivery:")
            print(json.dumps(d, indent=2, default=str))
            break
    else:
        print("No delivery found for this source")

    print(f"\nLog group: {log_group_name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage CloudWatch Logs delivery for AgentCore Runtime")
    parser.add_argument("--action", required=True, choices=["create", "delete", "get"])
    parser.add_argument("--region", required=True)
    parser.add_argument("--runtime-arn", help="Runtime ARN (required for create)")
    parser.add_argument("--runtime-id", required=True, help="Runtime ID")
    parser.add_argument("--account-id", help="AWS account ID (required for create)")
    args = parser.parse_args()

    logs_client = boto3.client("logs", region_name=args.region)

    if args.action == "create":
        if not args.runtime_arn or not args.account_id:
            print("Error: --runtime-arn and --account-id required for create")
            sys.exit(1)
        create_delivery(logs_client, args.runtime_arn, args.runtime_id, args.account_id, args.region)
    elif args.action == "delete":
        delete_delivery(logs_client, args.runtime_id)
    elif args.action == "get":
        get_delivery(logs_client, args.runtime_id)


if __name__ == "__main__":
    main()
