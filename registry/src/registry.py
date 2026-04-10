"""AWS Agent Registry client wrapping bedrock-agentcore-control and bedrock-agentcore."""

import time
from typing import Optional

import boto3


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
        session = boto3.Session(profile_name=profile, region_name=region)
        self.control = session.client("bedrock-agentcore-control")
        self.data = session.client("bedrock-agentcore")

    # -------------------------------------------------------------------------
    # Registries
    # -------------------------------------------------------------------------

    def list_registries(self) -> dict:
        """List all registries in the account/region."""
        return self.control.list_registries()

    # -------------------------------------------------------------------------
    # Records — control plane
    # -------------------------------------------------------------------------

    def create_record(self, name: str, descriptor_type: str, descriptors: dict) -> dict:
        """Create a new registry record."""
        return self.control.create_registry_record(
            registryId=self.registry_id,
            name=name,
            descriptorType=descriptor_type,
            descriptors=descriptors,
        )

    def get_record(self, record_id: str) -> dict:
        """Get a registry record by ID."""
        return self.control.get_registry_record(
            registryId=self.registry_id,
            recordId=record_id,
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
            print(f"  Status: {status}, waiting {poll_interval}s...", flush=True)
            time.sleep(poll_interval)

    def submit_for_approval(self, record_id: str) -> dict:
        """Submit a record for approval."""
        return self.control.submit_registry_record_for_approval(
            registryId=self.registry_id,
            recordId=record_id,
        )

    def approve_record(self, record_id: str, reason: str = "Approved") -> dict:
        """Approve a record."""
        return self.control.update_registry_record_status(
            registryId=self.registry_id,
            recordId=record_id,
            status="APPROVED",
            statusReason=reason,
        )

    def reject_record(self, record_id: str, reason: str = "Rejected") -> dict:
        """Reject a record."""
        return self.control.update_registry_record_status(
            registryId=self.registry_id,
            recordId=record_id,
            status="REJECTED",
            statusReason=reason,
        )

    def list_records(self) -> dict:
        """List all records in the registry."""
        return self.control.list_registry_records(registryId=self.registry_id)

    def delete_record(self, record_id: str) -> dict:
        """Delete a registry record."""
        return self.control.delete_registry_record(
            registryId=self.registry_id,
            recordId=record_id,
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
