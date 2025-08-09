import boto3
import click
import json
import logging
from datetime import datetime
from boto3.session import Session
from botocore.exceptions import ClientError

# constants
REQUIREMENTS_FILE = "requirements.txt"

# initialization
logging.getLogger("agentcore").setLevel(logging.INFO)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s (%(name)s) [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

class AgentCoreRuntime:
    def __init__(self):
        session = Session()
        region = session.region_name
        self.client_agentcore_cp = boto3.client('bedrock-agentcore-control', region_name=region)
        self.client_agentcore_dp = boto3.client('bedrock-agentcore', region_name=region)

    def find_runtime_by_name(self, name):
        list_response = self.client_agentcore_cp.list_agent_runtimes()
        target_runtime = [runtime for runtime in list_response['agentRuntimes'] if runtime['agentRuntimeName'] == name]
        if len(target_runtime) > 0:
            return target_runtime[0]
        return None

    def _configure_runtime_params(self, action: str, ecr_repo_uri: str, execution_role: str, server_protocol: str = "HTTP", runtime_name: str = None, runtime_id: str = None, env_vars: dict = {}, authorizer_configuration: dict = {}):
        params = {
            'agentRuntimeArtifact': {
                'containerConfiguration': {
                    'containerUri': ecr_repo_uri,
                }
            },
            'roleArn': execution_role,
            'networkConfiguration': {
                'networkMode': 'PUBLIC'
            },
            'protocolConfiguration': {
                'serverProtocol': server_protocol
            }
        }
        if action == "create":
            params['agentRuntimeName'] = runtime_name
        elif action == "update":
            params['agentRuntimeId'] = runtime_id
        if env_vars:
            params['environmentVariables'] = env_vars
        if authorizer_configuration:
            params['authorizerConfiguration'] = authorizer_configuration
        return params

    def create_runtime(self, runtime_name: str, ecr_repo_uri: str, execution_role: str, server_protocol: str = "HTTP", env_vars: dict = {}, authorizer_configuration: dict = {}):
        try:
            params = self._configure_runtime_params("create", ecr_repo_uri, execution_role, server_protocol, runtime_name=runtime_name, env_vars=env_vars, authorizer_configuration=authorizer_configuration)
            response = self.client_agentcore_cp.create_agent_runtime(**params)
            return response
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ConflictException':
                logging.warning(f"Agent runtime '{runtime_name}' already exists: {e}")
                response = self.find_runtime_by_name(runtime_name)
                return response
            else:
                logging.error(f"Error creating agent runtime: {e}")
                raise e

    def update_runtime(self, runtime_id: str, ecr_repo_uri: str, execution_role: str, server_protocol: str = "HTTP", env_vars: dict = {}, authorizer_configuration: dict = {}):
        try:
            params = self._configure_runtime_params("update", ecr_repo_uri, execution_role, server_protocol, runtime_id=runtime_id, env_vars=env_vars, authorizer_configuration=authorizer_configuration)
            response = self.client_agentcore_cp.update_agent_runtime(**params)
            return response
        except ClientError as e:
            logging.error(f"Error updating agent runtime: {e}")
            raise e

    def invoke(self, agent_arn, agent_version="DEFAULT", prompt="What is VO2 max?"):
        response = self.client_agentcore_dp.invoke_agent_runtime(
            agentRuntimeArn=agent_arn,
            qualifier=agent_version,
            payload=json.dumps({"prompt": prompt})
        )
        if "text/event-stream" in response.get("contentType", ""):
            content = []
            for line in response["response"].iter_lines(chunk_size=1):
                if line:
                    line = line.decode("utf-8")

                    if line.startswith("data: "):
                        line = line[6:]    # strip 'data: '
                        line = line[1:-1]  # strip beginning and ending quotes
                        logging.info(line)
                        content.append(line)
            print("".join(content))
        else:
            try:
                events = []
                for event in response.get("response", []):
                    events.append(event)
            except Exception as e:
                events = [f"Error reading EventStream: {e}"]
            print(json.loads(events[0].decode("utf-8")))

@click.command()
@click.option("--action", required=True, default="invoke", help="Action to perform")
@click.option("--runtime-name", help="Agent runtime name")
@click.option("--runtime-id", help="Agent runtime ID")
@click.option("--ecr-repo-uri", help="ECR repository URI")
@click.option("--execution-role", help="Execution role ARN")
@click.option("--server-protocol", help="Server protocol", default="HTTP")
@click.option("--env-vars", help="Environment variables")
@click.option("--authorizer-configuration", help="Authorizer configuration")
@click.option("--agent-arn", help="Agent ARN")
@click.option("--agent-version", help="Agent version")
@click.option("--prompt", help="Prompt to send to the agent")
def main(action, runtime_name, runtime_id, ecr_repo_uri, execution_role, server_protocol, env_vars, authorizer_configuration, agent_arn, agent_version, prompt):
    agentcore_runtime = AgentCoreRuntime()
    debug_vars = {
        "action": action,
        "runtime_name": runtime_name,
        "runtime_id": runtime_id,
        "ecr_repo_uri": ecr_repo_uri,
        "execution_role": execution_role,
        "server_protocol": server_protocol,
        "env_vars": env_vars,
        "authorizer_configuration": authorizer_configuration,
        "agent_arn": agent_arn,
        "agent_version": agent_version,
        "prompt": prompt
    }
    logging.debug(json.dumps(debug_vars, indent=4, cls=DateTimeEncoder))
    match action:
        case "create":
            env_vars = json.loads(env_vars) if env_vars else None
            authorizer_configuration = json.loads(authorizer_configuration) if authorizer_configuration else None
            logging.info(json.dumps({"runtime_name": runtime_name, "ecr_repo_uri": ecr_repo_uri, "execution_role": execution_role, "server_protocol": server_protocol, "env_vars": env_vars, "authorizer_configuration": authorizer_configuration}))
            response = agentcore_runtime.create_runtime(runtime_name, ecr_repo_uri, execution_role, server_protocol, env_vars, authorizer_configuration)
            logging.info(json.dumps(response, cls=DateTimeEncoder))
        case "update":
            env_vars = json.loads(env_vars) if env_vars else None
            authorizer_configuration = json.loads(authorizer_configuration) if authorizer_configuration else None
            logging.info(json.dumps({"runtime_name": runtime_name, "ecr_repo_uri": ecr_repo_uri, "execution_role": execution_role, "server_protocol": server_protocol, "env_vars": env_vars, "authorizer_configuration": authorizer_configuration}))
            response = agentcore_runtime.update_runtime(runtime_id, ecr_repo_uri, execution_role, server_protocol, env_vars, authorizer_configuration)
            logging.info(json.dumps(response, cls=DateTimeEncoder))
        case "invoke":
            logging.info(json.dumps({"agent_arn": agent_arn, "agent_version": agent_version}))
            agentcore_runtime.invoke(agent_arn, agent_version, prompt)
        case _:
            logging.info(json.dumps({"message": f"invalid action: {action}"}))

if __name__ == "__main__":
    main()
