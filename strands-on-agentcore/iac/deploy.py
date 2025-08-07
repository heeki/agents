import boto3
import click
import json
import logging
from datetime import datetime
from boto3.session import Session
from botocore.exceptions import ClientError

# constants
ENTRYPOINT = "src/agent.py"
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

    def create_runtime(self, runtime_name, ecr_repo_uri, execution_role):
        try:
            response = self.client_agentcore_cp.create_agent_runtime(
                agentRuntimeName=runtime_name,
                agentRuntimeArtifact={
                    'containerConfiguration': {
                        'containerUri': ecr_repo_uri,
                    }
                },
                roleArn=execution_role,
                networkConfiguration={
                    'networkMode': 'PUBLIC'
                },
                protocolConfiguration={
                    'serverProtocol': 'HTTP'
                },
                environmentVariables={
                    'AGENT_NAME': runtime_name
                }
            )
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
@click.option("--ecr-repo-uri", help="ECR repository URI")
@click.option("--execution-role", help="Execution role ARN")
@click.option("--agent-arn", help="Agent ARN")
@click.option("--agent-version", help="Agent version")
@click.option("--prompt", help="Prompt to send to the agent")
def main(action, runtime_name, ecr_repo_uri, execution_role, agent_arn, agent_version, prompt):
    agentcore_runtime = AgentCoreRuntime()
    logging.debug(f"Action: {action}")
    logging.debug(f"Runtime name: {runtime_name}")
    logging.debug(f"ECR repository URI: {ecr_repo_uri}")
    logging.debug(f"Execution role ARN: {execution_role}")
    match action:
        case "create":
            logging.info(json.dumps({"runtime_name": runtime_name, "ecr_repo_uri": ecr_repo_uri, "execution_role": execution_role}))
            response = agentcore_runtime.create_runtime(runtime_name, ecr_repo_uri, execution_role)
            logging.info(json.dumps(response, cls=DateTimeEncoder))
        case "invoke":
            logging.info(json.dumps({"agent_arn": agent_arn, "agent_version": agent_version}))
            agentcore_runtime.invoke(agent_arn, agent_version, prompt)
        case _:
            logging.info(json.dumps({"message": f"invalid action: {action}"}))

if __name__ == "__main__":
    main()
