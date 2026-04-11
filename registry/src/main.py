"""CLI for AWS Agent Registry interactions with Cognito JWT auth.

Environment variables (set via etc/environment.sh exports):
    REGISTRY_ID                 — Agent Registry ID (required for record commands)
    AWS_REGION                  — AWS region (default: us-east-1)
    AWS_PROFILE                 — AWS named profile (optional)
    COGNITO_WELLKNOWN_URL       — OIDC discovery endpoint for token acquisition
    COGNITO_M2M_CLIENT_ID       — Cognito M2M client ID
    COGNITO_M2M_CLIENT_SECRET   — Cognito M2M client secret
    COGNITO_SCOPE               — Space-separated OAuth2 scopes
    RECORD_CONFIG               — Path to record JSON config (default: etc/record.json)
    SEARCH_QUERY                — Search query string
    APPROVAL_REASON             — Reason text for approval
"""

import argparse
import copy
import json
import os
import sys
import time
from datetime import datetime
from typing import Any, Optional

import boto3

sys.path.insert(0, os.path.dirname(__file__))
from auth import OAuth2Client
from registry import RegistryClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean(obj: Any) -> Any:
    """Recursively convert datetime objects to ISO strings for JSON output."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean(v) for v in obj]
    return obj


def _print(obj: Any) -> None:
    """Print object as formatted JSON to stdout."""
    print(json.dumps(_clean(obj), indent=2))


def _record_id_from_arn(arn: str) -> str:
    """Extract the record ID from a registry record ARN."""
    return arn.split("/")[-1]


def _load_record_config() -> dict:
    """Load and prepare the record config from RECORD_CONFIG path."""
    path = os.environ.get("RECORD_CONFIG", "etc/record.json")
    with open(path) as f:
        config = json.load(f)

    # Convert inlineContent from dict to JSON string as required by the API.
    # Handles two layouts:
    #   flat:   descriptors.<type>.inlineContent (e.g. CUSTOM)
    #   nested: descriptors.<type>.<wrapper>.inlineContent (e.g. A2A agentCard, MCP serverSchema)
    descriptors = copy.deepcopy(config.get("descriptors", {}))
    for desc_value in descriptors.values():
        # Flat layout (CUSTOM)
        if isinstance(desc_value.get("inlineContent"), dict):
            desc_value["inlineContent"] = json.dumps(desc_value["inlineContent"])
        # Nested layout (A2A, MCP)
        for schema_obj in desc_value.values():
            if isinstance(schema_obj, dict) and isinstance(schema_obj.get("inlineContent"), dict):
                schema_obj["inlineContent"] = json.dumps(schema_obj["inlineContent"])

    config["descriptors"] = descriptors
    return config


def _build_auth_client() -> Optional[OAuth2Client]:
    well_known = os.environ.get("COGNITO_WELLKNOWN_URL", "")
    client_id = os.environ.get("COGNITO_M2M_CLIENT_ID", "")
    client_secret = os.environ.get("COGNITO_M2M_CLIENT_SECRET", "")
    if not all([well_known, client_id, client_secret]):
        return None
    return OAuth2Client(well_known, client_id, client_secret)


def _build_registry_client() -> RegistryClient:
    registry_id = os.environ.get("REGISTRY_ID", "")
    if not registry_id:
        print("ERROR: REGISTRY_ID environment variable is required", file=sys.stderr)
        sys.exit(1)
    return RegistryClient(
        registry_id=registry_id,
        region=os.environ.get("AWS_REGION", "us-east-1"),
        profile=os.environ.get("AWS_PROFILE"),
    )


def _require_record_id(args: argparse.Namespace) -> str:
    record_id = getattr(args, "record_id", None) or os.environ.get("RECORD_ID", "")
    if not record_id:
        print("ERROR: --record-id or RECORD_ID environment variable required", file=sys.stderr)
        sys.exit(1)
    return record_id


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def cmd_token(args: argparse.Namespace) -> None:
    """Acquire and print a Cognito M2M access token."""
    auth = _build_auth_client()
    if not auth:
        print(
            "ERROR: COGNITO_WELLKNOWN_URL, COGNITO_M2M_CLIENT_ID, and "
            "COGNITO_M2M_CLIENT_SECRET must all be set",
            file=sys.stderr,
        )
        sys.exit(1)
    scope = os.environ.get("COGNITO_SCOPE", "")
    payload = auth.token_payload(scope=scope)
    _print(payload)


def cmd_record_create(args: argparse.Namespace) -> None:
    """Create a registry record and wait for it to leave CREATING state."""
    config = _load_record_config()
    client = _build_registry_client()

    resp = client.create_record(
        name=config["name"],
        protocol=config["protocol"],
        descriptors=config["descriptors"],
        record_version=config.get("version") or config.get("recordVersion", "1.0"),
        description=config.get("description"),
    )
    record_id = _record_id_from_arn(resp["registryRecordArn"])
    print(f"Record created: {record_id}", file=sys.stderr)

    print("Waiting for record to leave CREATING state...", file=sys.stderr)
    rec = client.wait_for_record(record_id)
    print(f"Record status: {rec.get('status')}", file=sys.stderr)

    # Merge and surface record_id at the top level for easy jq extraction
    output = {**_clean(resp), **_clean(rec), "record_id": record_id}
    _print(output)


def cmd_record_get(args: argparse.Namespace) -> None:
    """Get a registry record by ID."""
    record_id = _require_record_id(args)
    client = _build_registry_client()
    _print(client.get_record(record_id))


def cmd_record_submit(args: argparse.Namespace) -> None:
    """Submit a record for approval."""
    record_id = _require_record_id(args)
    client = _build_registry_client()
    resp = client.submit_for_approval(record_id)
    print(f"Submitted record {record_id} for approval", file=sys.stderr)
    _print(resp)


def cmd_record_approve(args: argparse.Namespace) -> None:
    """Approve a record."""
    record_id = _require_record_id(args)
    reason = getattr(args, "reason", None) or os.environ.get("APPROVAL_REASON", "Approved")
    client = _build_registry_client()
    resp = client.approve_record(record_id, reason=reason)
    print(f"Approved record {record_id}", file=sys.stderr)
    _print(resp)


def cmd_record_reject(args: argparse.Namespace) -> None:
    """Reject a record."""
    record_id = _require_record_id(args)
    reason = getattr(args, "reason", None) or os.environ.get("REJECTION_REASON", "Rejected")
    client = _build_registry_client()
    resp = client.reject_record(record_id, reason=reason)
    print(f"Rejected record {record_id}", file=sys.stderr)
    _print(resp)


def cmd_record_list(args: argparse.Namespace) -> None:
    """List all registry records."""
    client = _build_registry_client()
    _print(client.list_records())


def cmd_record_search(args: argparse.Namespace) -> None:
    """Search approved registry records."""
    query = getattr(args, "query", None) or os.environ.get("SEARCH_QUERY", "")
    if not query:
        print("ERROR: --query or SEARCH_QUERY required", file=sys.stderr)
        sys.exit(1)
    max_results = getattr(args, "max_results", 10)
    client = _build_registry_client()
    _print(client.search_records(query, max_results=max_results))


def cmd_record_delete(args: argparse.Namespace) -> None:
    """Delete a registry record."""
    record_id = _require_record_id(args)
    client = _build_registry_client()
    resp = client.delete_record(record_id)
    print(f"Deleted record {record_id}", file=sys.stderr)
    _print(resp)


def cmd_registry_list(args: argparse.Namespace) -> None:
    """List all registries in the account/region."""
    session = boto3.Session(
        profile_name=os.environ.get("AWS_PROFILE"),
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )
    control = session.client("bedrock-agentcore-control")
    _print(_clean(control.list_registries()))


def cmd_workflow(args: argparse.Namespace) -> None:
    """Run the full end-to-end registry workflow.

    Steps:
        0. Authenticate — acquire Cognito M2M token
        1. Create record — POST record config, wait for ACTIVE
        2. Submit for approval
        3. Approve
        4. Wait 30s for search index propagation
        5. List records via control plane
        6. Search approved records via data plane
    """
    config = _load_record_config()
    search_query = os.environ.get("SEARCH_QUERY", "weather")
    approval_reason = os.environ.get("APPROVAL_REASON", "Approved for testing")

    auth = _build_auth_client()
    client = _build_registry_client()

    # Step 0: Authenticate
    token_info: dict = {}
    if auth:
        print("\n=== Step 0: Authenticate ===", file=sys.stderr)
        scope = os.environ.get("COGNITO_SCOPE", "")
        token_info = auth.token_payload(scope=scope)
        print(f"  Token type : {token_info.get('token_type')}", file=sys.stderr)
        print(f"  Expires in : {token_info.get('expires_in')}s", file=sys.stderr)
        print(f"  Scope      : {token_info.get('scope', scope)}", file=sys.stderr)
    else:
        print("\n=== Step 0: Skipping auth (no Cognito env vars set) ===", file=sys.stderr)

    # Step 1: Create record
    print("\n=== Step 1: Create Record ===", file=sys.stderr)
    resp = client.create_record(
        name=config["name"],
        protocol=config["protocol"],
        descriptors=config["descriptors"],
        record_version=config.get("version") or config.get("recordVersion", "1.0"),
        description=config.get("description"),
    )
    record_id = _record_id_from_arn(resp["registryRecordArn"])
    print(f"  Record created: {record_id}", file=sys.stderr)

    print("  Waiting for record to leave CREATING state...", file=sys.stderr)
    rec = client.wait_for_record(record_id)
    print(f"  Record status: {rec.get('status')}", file=sys.stderr)

    # Step 2: Submit for approval
    print("\n=== Step 2: Submit for Approval ===", file=sys.stderr)
    client.submit_for_approval(record_id)
    print("  Submitted", file=sys.stderr)

    # Step 3: Approve
    print("\n=== Step 3: Approve ===", file=sys.stderr)
    client.approve_record(record_id, reason=approval_reason)
    print("  Approved", file=sys.stderr)

    # Wait for search index propagation
    print("\n=== Waiting 30s for search index propagation ===", file=sys.stderr)
    time.sleep(30)

    # Step 4: List records
    print("\n=== Step 4: List Records (control plane) ===", file=sys.stderr)
    list_result = client.list_records()
    count = len(list_result.get("registryRecords", []))
    print(f"  Found {count} record(s)", file=sys.stderr)

    # Step 5: Search records
    print(f"\n=== Step 5: Search Records (query='{search_query}') ===", file=sys.stderr)
    search_result = client.search_records(search_query)
    found = len(search_result.get("registryRecords", []))
    print(f"  Found {found} matching record(s)", file=sys.stderr)

    _print({
        "record_id": record_id,
        "record_arn": resp.get("registryRecordArn"),
        "token_type": token_info.get("token_type"),
        "list_result": _clean(list_result),
        "search_result": _clean(search_result),
    })


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def _add_record_id_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--record-id", help="Registry record ID (overrides RECORD_ID env var)")


def _add_reason_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--reason", help="Status reason text")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AWS Agent Registry CLI with Cognito JWT auth",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("token", help="Acquire a Cognito M2M access token")
    sub.add_parser("record.create", help="Create a registry record (reads RECORD_CONFIG)")
    p = sub.add_parser("record.get", help="Get a registry record")
    _add_record_id_arg(p)
    p = sub.add_parser("record.submit", help="Submit a record for approval")
    _add_record_id_arg(p)
    p = sub.add_parser("record.approve", help="Approve a record")
    _add_record_id_arg(p)
    _add_reason_arg(p)
    p = sub.add_parser("record.reject", help="Reject a record")
    _add_record_id_arg(p)
    _add_reason_arg(p)
    sub.add_parser("record.list", help="List all records in the registry")
    p = sub.add_parser("record.search", help="Search approved records")
    p.add_argument("--query", help="Search query (overrides SEARCH_QUERY env var)")
    p.add_argument("--max-results", type=int, default=10, dest="max_results")
    p = sub.add_parser("record.delete", help="Delete a registry record")
    _add_record_id_arg(p)
    sub.add_parser("registry.list", help="List all registries in the account/region")
    sub.add_parser("workflow", help="Run the full end-to-end registry workflow")

    args = parser.parse_args()

    handlers = {
        "token": cmd_token,
        "record.create": cmd_record_create,
        "record.get": cmd_record_get,
        "record.submit": cmd_record_submit,
        "record.approve": cmd_record_approve,
        "record.reject": cmd_record_reject,
        "record.list": cmd_record_list,
        "record.search": cmd_record_search,
        "record.delete": cmd_record_delete,
        "registry.list": cmd_registry_list,
        "workflow": cmd_workflow,
    }

    handlers[args.command](args)


if __name__ == "__main__":
    main()
