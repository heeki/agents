#!/usr/bin/env python3
"""AgentCore Runtime Deployment Helper.

Manages AgentCore runtime creation, updates, and invocation for the
A2A multi-agent fitness system.
"""

import boto3
import click
import json
import logging
from datetime import datetime
from boto3.session import Session
from botocore.exceptions import ClientError

# Initialization
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class DateTimeEncoder(json.JSONEncoder):
    """JSON encoder that handles datetime objects."""

    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class AgentCoreRuntime:
    """Manages AgentCore runtime operations."""

    def __init__(self, region: str | None = None):
        """Initialize the AgentCore client.

        Args:
            region: AWS region. Defaults to session default.
        """
        session = Session()
        self.region = region or session.region_name
        self.client_cp = boto3.client(
            "bedrock-agentcore-control", region_name=self.region
        )
        self.client_dp = boto3.client("bedrock-agentcore", region_name=self.region)

    def list_runtimes(self) -> list[dict]:
        """List all AgentCore runtimes."""
        response = self.client_cp.list_agent_runtimes()
        return response.get("agentRuntimes", [])

    def find_runtime_by_name(self, name: str) -> dict | None:
        """Find a runtime by name.

        Args:
            name: Runtime name to search for.

        Returns:
            Runtime info dict or None if not found.
        """
        runtimes = self.list_runtimes()
        for runtime in runtimes:
            if runtime.get("agentRuntimeName") == name:
                return runtime
        return None

    def create_runtime(
        self,
        runtime_name: str,
        ecr_repo_uri: str,
        execution_role: str,
        server_protocol: str = "HTTP",
        env_vars: dict | None = None,
        authorizer_config: dict | None = None,
    ) -> dict:
        """Create a new AgentCore runtime.

        Args:
            runtime_name: Name for the runtime.
            ecr_repo_uri: ECR container image URI.
            execution_role: IAM role ARN for execution.
            server_protocol: HTTP or MCP.
            env_vars: Environment variables for the container.
            authorizer_config: JWT authorizer configuration.

        Returns:
            Runtime creation response.
        """
        params = {
            "agentRuntimeName": runtime_name,
            "agentRuntimeArtifact": {
                "containerConfiguration": {
                    "containerUri": ecr_repo_uri,
                }
            },
            "roleArn": execution_role,
            "networkConfiguration": {"networkMode": "PUBLIC"},
            "protocolConfiguration": {"serverProtocol": server_protocol},
        }

        if env_vars:
            params["environmentVariables"] = env_vars

        if authorizer_config:
            params["authorizerConfiguration"] = authorizer_config

        try:
            response = self.client_cp.create_agent_runtime(**params)
            logger.info(f"Created runtime: {runtime_name}")
            return response
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConflictException":
                logger.warning(f"Runtime '{runtime_name}' already exists")
                existing = self.find_runtime_by_name(runtime_name)
                if existing:
                    return existing
            raise

    def update_runtime(
        self,
        runtime_id: str,
        ecr_repo_uri: str,
        execution_role: str,
        server_protocol: str = "HTTP",
        env_vars: dict | None = None,
        authorizer_config: dict | None = None,
    ) -> dict:
        """Update an existing AgentCore runtime.

        Args:
            runtime_id: ID of the runtime to update.
            ecr_repo_uri: New ECR container image URI.
            execution_role: IAM role ARN for execution.
            server_protocol: HTTP or MCP.
            env_vars: Environment variables for the container.
            authorizer_config: JWT authorizer configuration.

        Returns:
            Runtime update response.
        """
        params = {
            "agentRuntimeId": runtime_id,
            "agentRuntimeArtifact": {
                "containerConfiguration": {
                    "containerUri": ecr_repo_uri,
                }
            },
            "roleArn": execution_role,
            "networkConfiguration": {"networkMode": "PUBLIC"},
            "protocolConfiguration": {"serverProtocol": server_protocol},
        }

        if env_vars:
            params["environmentVariables"] = env_vars

        if authorizer_config:
            params["authorizerConfiguration"] = authorizer_config

        response = self.client_cp.update_agent_runtime(**params)
        logger.info(f"Updated runtime: {runtime_id}")
        return response

    def delete_runtime(self, runtime_id: str) -> dict:
        """Delete an AgentCore runtime.

        Args:
            runtime_id: ID of the runtime to delete.

        Returns:
            Deletion response.
        """
        response = self.client_cp.delete_agent_runtime(agentRuntimeId=runtime_id)
        logger.info(f"Deleted runtime: {runtime_id}")
        return response

    def invoke(
        self,
        agent_arn: str,
        prompt: str,
        qualifier: str = "DEFAULT",
    ) -> None:
        """Invoke an AgentCore runtime.

        Args:
            agent_arn: ARN of the agent runtime.
            prompt: Prompt to send to the agent.
            qualifier: Version qualifier (default: DEFAULT).
        """
        response = self.client_dp.invoke_agent_runtime(
            agentRuntimeArn=agent_arn,
            qualifier=qualifier,
            payload=json.dumps({"prompt": prompt}),
        )

        content_type = response.get("contentType", "")

        if "text/event-stream" in content_type:
            # Handle SSE streaming response
            content = []
            for line in response["response"].iter_lines(chunk_size=1):
                if line:
                    line = line.decode("utf-8")
                    if line.startswith("data: "):
                        data = line[6:]
                        # Remove quotes if present
                        if data.startswith('"') and data.endswith('"'):
                            data = data[1:-1]
                        logger.info(data)
                        content.append(data)
            print("".join(content))
        else:
            # Handle JSON response
            try:
                events = []
                for event in response.get("response", []):
                    events.append(event)
                if events:
                    result = json.loads(events[0].decode("utf-8"))
                    print(json.dumps(result, indent=2))
            except Exception as e:
                logger.error(f"Error reading response: {e}")


@click.command()
@click.option("--action", required=True, help="Action: create, update, delete, list, invoke")
@click.option("--runtime-name", help="Runtime name (for create)")
@click.option("--runtime-id", help="Runtime ID (for update/delete)")
@click.option("--ecr-repo-uri", help="ECR repository URI")
@click.option("--execution-role", help="IAM execution role ARN")
@click.option("--server-protocol", default="HTTP", help="Server protocol (HTTP/MCP)")
@click.option("--env-vars", help="Environment variables as JSON")
@click.option("--authorizer-configuration", help="Authorizer config as JSON")
@click.option("--agent-arn", help="Agent ARN (for invoke)")
@click.option("--agent-version", default="DEFAULT", help="Agent version (for invoke)")
@click.option("--prompt", help="Prompt to send (for invoke)")
def main(
    action: str,
    runtime_name: str | None,
    runtime_id: str | None,
    ecr_repo_uri: str | None,
    execution_role: str | None,
    server_protocol: str,
    env_vars: str | None,
    authorizer_configuration: str | None,
    agent_arn: str | None,
    agent_version: str,
    prompt: str | None,
):
    """AgentCore Runtime Management CLI."""
    runtime = AgentCoreRuntime()

    # Parse JSON options
    parsed_env_vars = json.loads(env_vars) if env_vars else None
    parsed_auth_config = (
        json.loads(authorizer_configuration) if authorizer_configuration else None
    )

    if action == "create":
        if not all([runtime_name, ecr_repo_uri, execution_role]):
            raise click.UsageError(
                "create requires --runtime-name, --ecr-repo-uri, --execution-role"
            )
        response = runtime.create_runtime(
            runtime_name,
            ecr_repo_uri,
            execution_role,
            server_protocol,
            parsed_env_vars,
            parsed_auth_config,
        )
        print(json.dumps(response, indent=2, cls=DateTimeEncoder))

    elif action == "update":
        if not all([runtime_id, ecr_repo_uri, execution_role]):
            raise click.UsageError(
                "update requires --runtime-id, --ecr-repo-uri, --execution-role"
            )
        response = runtime.update_runtime(
            runtime_id,
            ecr_repo_uri,
            execution_role,
            server_protocol,
            parsed_env_vars,
            parsed_auth_config,
        )
        print(json.dumps(response, indent=2, cls=DateTimeEncoder))

    elif action == "delete":
        if not runtime_id:
            raise click.UsageError("delete requires --runtime-id")
        response = runtime.delete_runtime(runtime_id)
        print(json.dumps(response, indent=2, cls=DateTimeEncoder))

    elif action == "list":
        runtimes = runtime.list_runtimes()
        print(json.dumps(runtimes, indent=2, cls=DateTimeEncoder))

    elif action == "invoke":
        if not all([agent_arn, prompt]):
            raise click.UsageError("invoke requires --agent-arn, --prompt")
        runtime.invoke(agent_arn, prompt, agent_version)

    else:
        raise click.UsageError(f"Unknown action: {action}")


if __name__ == "__main__":
    main()
