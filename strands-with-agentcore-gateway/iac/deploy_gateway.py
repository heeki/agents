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

class AgentCoreGateway:
    def __init__(self):
        session = Session()
        region = session.region_name
        self.client_agentcore_cp = boto3.client('bedrock-agentcore-control', region_name=region)
        self.client_agentcore_dp = boto3.client('bedrock-agentcore', region_name=region)

    def find_gateway_by_name(self, name):
        list_response = self.client_agentcore_cp.list_gateways()
        target_gateway = [gateway for gateway in list_response['items'] if gateway['name'] == name]
        if len(target_gateway) > 0:
            return target_gateway[0]
        return None

    def create_gateway(self, gateway_name: str, description: str = "", execution_role: str = "", authorizer_configuration: dict = {}):
        try:
            response = self.client_agentcore_cp.create_gateway(
                name=gateway_name,
                description=description,
                roleArn=execution_role,
                protocolType='MCP',
                authorizerType='CUSTOM_JWT',
                authorizerConfiguration=authorizer_configuration
            )
            return response
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ConflictException':
                logging.warning(f"Agent gateway '{gateway_name}' already exists: {e}")
                response = self.find_gateway_by_name(gateway_name)
                return response
            else:
                logging.error(f"Error creating agent gateway: {e}")
            raise e

    def update_gateway(self, gateway_id: str, gateway_name: str = "", description: str = "", execution_role: str = "", authorizer_configuration: dict = {}):
        try:
            response = self.client_agentcore_cp.update_gateway(
                gatewayIdentifier=gateway_id,
                name=gateway_name,
                description=description,
                roleArn=execution_role,
                protocolType='MCP',
                authorizerType='CUSTOM_JWT',
                authorizerConfiguration=authorizer_configuration
            )
            return response
        except ClientError as e:
            logging.error(f"Error updating agent gateway: {e}")
            raise e

    def create_gateway_target(self, gateway_name: str, description: str = "", target_configuration: dict = {}, authorizer_configuration: dict = {}):
        try:
            response = self.client_agentcore_cp.create_gateway_target(
                name=gateway_name,
                description=description,
                targetConfiguration=target_configuration,
                credentialProviderConfigurations=[authorizer_configuration]
            )
            return response
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ConflictException':
                logging.warning(f"Agent Gateway '{gateway_name}' already exists: {e}")
                response = self.find_gateway_by_name(gateway_name)
                return response
            else:
                logging.error(f"Error creating agent gateway: {e}")
                raise e

@click.command()
@click.option("--action", required=True, default="invoke", help="Action to perform")
@click.option("--gateway-name", help="Gateway name")
@click.option("--gateway-id", help="Gateway ID")
@click.option("--description", help="Gateway description")
@click.option("--execution-role", help="Execution role")
@click.option("--authorizer-configuration", help="Authorizer configuration")
def main(action, gateway_name, gateway_id, description, execution_role, authorizer_configuration):
    agentcore_gateway = AgentCoreGateway()
    debug_vars = {
        "action": action,
        "gateway_name": gateway_name,
        "gateway_id": gateway_id,
        "description": description,
        "execution_role": execution_role,
        "authorizer_configuration": authorizer_configuration,
    }
    logging.debug(json.dumps(debug_vars, indent=4, cls=DateTimeEncoder))
    match action:
        case "create":
            authorizer_configuration = json.loads(authorizer_configuration) if authorizer_configuration else None
            logging.info(json.dumps({"gateway_name": gateway_name, "description": description, "execution_role": execution_role, "authorizer_configuration": authorizer_configuration}))
            response = agentcore_gateway.create_gateway(gateway_name, description, execution_role, authorizer_configuration)
            logging.info(json.dumps(response, cls=DateTimeEncoder))
        case "update":
            authorizer_configuration = json.loads(authorizer_configuration) if authorizer_configuration else None
            response = agentcore_gateway.update_gateway(gateway_id, gateway_name, description, execution_role, authorizer_configuration)
            logging.info(json.dumps(response, cls=DateTimeEncoder))
        case _:
            logging.info(json.dumps({"message": f"invalid action: {action}"}))

if __name__ == "__main__":
    main()
