"""AWS Agent Registry client wrapping bedrock-agentcore-control and bedrock-agentcore."""

import json
import time
from typing import Optional

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.httpsession import URLLib3Session


# botocore >= 1.42 renamed several params at the Python/client-model level but the service
# wire API still uses the original names.  We rewrite request bodies before signing and
# patch response bodies after parsing.
_SDK_TO_WIRE = {
    "protocol": "descriptorType",
}
_MCP_SDK_TO_WIRE = {
    "serverSchema": "server",
    "toolSchema": "tools",
}

# Wire field names in responses → Python names the rest of the code expects.
_WIRE_TO_SDK_RESPONSE = {
    "recordArn": "registryRecordArn",
    "recordId":  "registryRecordId",
    "descriptorType": "protocol",
}


def _fix_registry_wire_params(request, **kwargs):
    """Rewrite SDK-renamed body fields to their wire names before signing.

    before-sign provides an AWSRequest whose body is backed by request.data,
    so we update request.data rather than request.body (which is read-only).
    """
    raw = getattr(request, "data", None) or getattr(request, "body", None)
    if not raw:
        return
    try:
        body = json.loads(raw)
    except (ValueError, TypeError):
        return

    changed = False

    for sdk_name, wire_name in _SDK_TO_WIRE.items():
        if sdk_name in body:
            body[wire_name] = body.pop(sdk_name)
            changed = True

    mcp = body.get("descriptors", {}).get("mcp")
    if mcp:
        for sdk_name, wire_name in _MCP_SDK_TO_WIRE.items():
            if sdk_name in mcp:
                mcp[wire_name] = mcp.pop(sdk_name)
                changed = True
        # Strip schemaVersion from both server and tools before sending to wire.
        # botocore requires schemaVersion client-side for param validation, but the service
        # rejects all known explicit values (including "auto"). Omitting it triggers
        # auto-detection from inlineContent (works when content conforms to the official
        # MCP schema).
        for sub in ("server", "tools"):
            if sub in mcp and "schemaVersion" in mcp[sub]:
                del mcp[sub]["schemaVersion"]
                changed = True


    if changed:
        encoded = json.dumps(body).encode()
        # before-sign: body is backed by request.data
        # before-send: body is directly settable on AWSPreparedRequest
        if hasattr(request, "data"):
            request.data = encoded
        else:
            request.body = encoded
        request.headers["Content-Length"] = str(len(encoded))


def _fix_registry_response(http_response, parsed, **kwargs):
    """Re-parse the raw response body and inject wire-named fields under their
    Python SDK names, since botocore >= 1.42 looks for renamed keys that the
    service doesn't send yet.
    """
    try:
        raw = json.loads(http_response.text)
    except (ValueError, AttributeError):
        return

    for wire_name, sdk_name in _WIRE_TO_SDK_RESPONSE.items():
        if wire_name in raw and sdk_name not in parsed:
            parsed[sdk_name] = raw[wire_name]

    # Surface any other fields from the raw body that botocore dropped.
    for key, value in raw.items():
        if key not in parsed and key not in _WIRE_TO_SDK_RESPONSE:
            parsed[key] = value


class RegistryClient:
    """Wraps the two boto3 clients needed for registry operations.

    Args:
        registry_id: The Agent Registry ID.
        region: AWS region.
        profile: Optional AWS named profile.
    """

    def __init__(
        self,
        registry_id: str,
        region: str,
        profile: Optional[str] = None,
    ) -> None:
        self.registry_id = registry_id
        self._region = region
        session = boto3.Session(profile_name=profile, region_name=region)
        self._credentials = session.get_credentials()
        self.control = session.client("bedrock-agentcore-control")
        self.data = session.client("bedrock-agentcore")
        self._http = URLLib3Session()

        # Rewrite SDK-renamed body fields BEFORE signing so the SigV4 signature
        # covers the correct payload (wire names the service actually expects).
        for op in ("CreateRegistryRecord", "UpdateRegistryRecord", "ListRegistryRecords"):
            self.control.meta.events.register(
                f"before-sign.bedrock-agentcore-control.{op}",
                _fix_registry_wire_params,
            )

        # Re-inject wire-named response fields under their Python SDK names.
        self.control.meta.events.register(
            "after-call.bedrock-agentcore-control.*",
            _fix_registry_response,
        )

    # -------------------------------------------------------------------------
    # Registries
    # -------------------------------------------------------------------------

    def list_registries(self) -> dict:
        """List all registries in the account/region."""
        return self.control.list_registries()

    # -------------------------------------------------------------------------
    # Records — control plane
    # -------------------------------------------------------------------------

    def create_record(self, name: str, protocol: str, descriptors: dict, record_version: str, description: Optional[str] = None) -> dict:
        """Create a new registry record."""
        kwargs = dict(
            registryIdentifier=self.registry_id,
            name=name,
            protocol=protocol,
            descriptors=descriptors,
            recordVersion=record_version,
        )
        if description:
            kwargs["description"] = description
        return self.control.create_registry_record(**kwargs)

    def get_record(self, record_id: str) -> dict:
        """Get a registry record by ID."""
        return self.control.get_registry_record(
            registryIdentifier=self.registry_id,
            recordIdentifier=record_id,
        )

    def wait_for_record(self, record_id: str, poll_interval: int = 5) -> dict:
        """Poll until the record leaves the CREATING state.

        Args:
            record_id: Registry record ID.
            poll_interval: Seconds between status checks.

        Returns:
            The get_record response once status is no longer CREATING.
        """
        while True:
            rec = self.get_record(record_id)
            status = rec.get("status", "")
            if status != "CREATING":
                return rec
            print(f"  Status: {status}, waiting {poll_interval}s...", flush=True, file=__import__("sys").stderr)
            time.sleep(poll_interval)

    def submit_for_approval(self, record_id: str) -> dict:
        """Submit a record for approval."""
        return self.control.submit_registry_record_for_approval(
            registryIdentifier=self.registry_id,
            recordIdentifier=record_id,
        )

    def _update_record_status(self, record_id: str, status: str, reason: str) -> dict:
        """Update a record's status via direct SigV4-signed request.

        botocore's UpdateRegistryRecordStatus model is broken in three ways:
        wrong HTTP method (PUT instead of PATCH), wrong SigV4 signing service
        (bedrock-agentcore-control instead of bedrock-agentcore), and missing
        required wire field (statusReason). We bypass botocore entirely.
        """
        url = (
            f"https://bedrock-agentcore-control.{self._region}.amazonaws.com"
            f"/registries/{self.registry_id}/records/{record_id}/status"
        )
        body = json.dumps({"status": status, "statusReason": reason})
        request = AWSRequest(
            method="PATCH", url=url, data=body,
            headers={"Content-Type": "application/json"},
        )
        SigV4Auth(self._credentials.get_frozen_credentials(), "bedrock-agentcore", self._region).add_auth(request)
        resp = self._http.send(request.prepare())
        parsed = json.loads(resp.text)
        if resp.status_code >= 400:
            raise Exception(f"UpdateRegistryRecordStatus failed ({resp.status_code}): {parsed}")
        return parsed

    def approve_record(self, record_id: str, reason: str = "Approved") -> dict:
        """Approve a record."""
        return self._update_record_status(record_id, "APPROVED", reason)

    def reject_record(self, record_id: str, reason: str = "Rejected") -> dict:
        """Reject a record."""
        return self._update_record_status(record_id, "REJECTED", reason)

    def list_records(self) -> dict:
        """List all records in the registry."""
        return self.control.list_registry_records(registryIdentifier=self.registry_id)

    def delete_record(self, record_id: str) -> dict:
        """Delete a registry record."""
        return self.control.delete_registry_record(
            registryIdentifier=self.registry_id,
            recordIdentifier=record_id,
        )

    # -------------------------------------------------------------------------
    # Records — data plane (search)
    # -------------------------------------------------------------------------

    def search_records(self, query: str, max_results: int = 10) -> dict:
        """Search approved records across one or more registries."""
        return self.data.search_registry_records(
            registryIds=[self.registry_id],
            searchQuery=query,
            maxResults=max_results,
        )
