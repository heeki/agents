import boto3
import click
import json
import logging
import yaml
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

    def find_gateway_target_by_name(self, gateway_id: str, target_name: str):
        list_response = self.client_agentcore_cp.list_gateway_targets(gatewayIdentifier=gateway_id)
        target_gateway_target = [gateway_target for gateway_target in list_response['items'] if gateway_target['name'] == target_name]
        if len(target_gateway_target) > 0:
            return target_gateway_target[0]
        return None

    def create_gateway(self,
        gateway_name: str,
        description: str = "",
        execution_role: str = "",
        authorizer_configuration: dict = {}
    ):
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

    def update_gateway(self,
        gateway_id: str,
        gateway_name: str = "",
        description: str = "",
        execution_role: str = "",
        authorizer_configuration: dict = {}
    ):
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

    def _configure_credential_provider_params(self,
        provider_name: str = "",
        issuer_url: str = "",
        authorization_endpoint: str = "",
        token_endpoint: str = "",
        client_id: str = "",
        client_secret: str = ""
    ):
        params = {
            'name': provider_name,
            'credentialProviderVendor': 'CustomOauth2',
            'oauth2ProviderConfigInput': {
                'customOauth2ProviderConfig': {
                    'oauthDiscovery': {
                        'authorizationServerMetadata': {
                            'issuer': issuer_url,
                            'authorizationEndpoint': authorization_endpoint,
                            'tokenEndpoint': token_endpoint,
                            'responseTypes': ['token']
                        }
                    },
                    'clientId': client_id,
                    'clientSecret': client_secret
                }
            }
        }
        return params

    def find_credential_provider_by_name(self, provider_name: str):
        list_response = self.client_agentcore_cp.list_oauth2_credential_providers()
        credential_provider = [provider for provider in list_response['credentialProviders'] if provider['name'] == provider_name]
        if len(credential_provider) > 0:
            return credential_provider[0]
        return None

    def create_credential_provider(self, credential_provider_inputs: dict = {}):
        try:
            params = self._configure_credential_provider_params(**credential_provider_inputs)
            logging.info(json.dumps(params, indent=4, cls=DateTimeEncoder))
            response = self.client_agentcore_cp.create_oauth2_credential_provider(**params)
            return response['credentialProviderArn']
        except ClientError as e:
            error_message = e.response['Error']['Message']
            if "already exists" in error_message:
                # Get existing credential provider ARN
                response = self.client_agentcore_cp.list_oauth2_credential_providers()
                credential_provider = self.find_credential_provider_by_name(credential_provider_inputs['provider_name'])
                return credential_provider['credentialProviderArn']
            logging.error(f"Error creating credential provider: {e}")
            raise e

    def _configure_credential_provider_configurations(self, credential_provider_arn: str):
        return [
            {
                'credentialProviderType': 'OAUTH',
                'credentialProvider': {
                    'oauthCredentialProvider': {
                        'providerArn': credential_provider_arn,
                        'scopes': []
                    }
                }
            }
        ]

    def _configure_gateway_target_params(self, target_type: str, openapi_specification: dict = {}):
        params = {
            'mcp': {}
        }
        if target_type == "openApiSchema":
            params['mcp']['openApiSchema'] = {
                'inlinePayload': json.dumps(openapi_specification)
            }
        elif target_type == 'lambda':
            params['mcp']['lambda'] = {
                'lambdaArn': '',
                'toolSchema': {
                    'inlinePayload': [
                        {
                            'name': 'string',
                            'description': 'string',
                            'inputSchema': {
                                'type': 'string'|'number'|'object'|'array'|'boolean'|'integer',
                                'properties': {
                                    'string': {'... recursive ...'}
                                },
                                'required': [
                                    'string',
                                ],
                                'items': {'... recursive ...'},
                                'description': 'string'
                            },
                            'outputSchema': {
                                'type': 'string'|'number'|'object'|'array'|'boolean'|'integer',
                                'properties': {
                                    'string': {'... recursive ...'}
                                },
                                'required': [
                                    'string',
                                ],
                                'items': {'... recursive ...'},
                                'description': 'string'
                            }
                        },
                    ]
                }
            }
        return params

    def create_gateway_target(self,
        gateway_id: str,
        target_name: str = "",
        target_description: str = "",
        openapi_file: str = "",
        credential_provider_inputs: dict = {}
    ):
        try:
            with open(openapi_file, 'r') as f:
                openapi_specification = yaml.safe_load(f)
            target_configuration = self._configure_gateway_target_params("openApiSchema", openapi_specification)
            logging.info(json.dumps(target_configuration, indent=4, cls=DateTimeEncoder))
            credential_provider_arn = self.create_credential_provider(credential_provider_inputs)
            credential_provider_configurations = self._configure_credential_provider_configurations(credential_provider_arn)
            logging.info(json.dumps(credential_provider_configurations, indent=4, cls=DateTimeEncoder))
            response = self.client_agentcore_cp.create_gateway_target(
                gatewayIdentifier=gateway_id,
                name=target_name,
                description=target_description,
                targetConfiguration=target_configuration,
                credentialProviderConfigurations=credential_provider_configurations
            )
            return response
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ConflictException':
                logging.warning(f"Agent Gateway Target '{target_name}' already exists: {e}")
                response = self.find_gateway_target_by_name(gateway_id, target_name)
                return response
            else:
                logging.error(f"Error creating agent gateway: {e}")
                raise e

    def update_gateway_target(self,
        gateway_id: str,
        target_id: str = "",
        target_name: str = "",
        target_description: str = "",
        openapi_file: str = "",
        credential_provider_inputs: dict = {}
    ):
        try:
            with open(openapi_file, 'r') as f:
                openapi_specification = yaml.safe_load(f)
            target_configuration = self._configure_gateway_target_params("openApiSchema", openapi_specification)
            logging.info(json.dumps(target_configuration, indent=4, cls=DateTimeEncoder))
            credential_provider_arn = self.create_credential_provider(credential_provider_inputs)
            credential_provider_configurations = self._configure_credential_provider_configurations(credential_provider_arn)
            logging.info(json.dumps(credential_provider_configurations, indent=4, cls=DateTimeEncoder))
            response = self.client_agentcore_cp.update_gateway_target(
                gatewayIdentifier=gateway_id,
                targetId=target_id,
                name=target_name,
                description=target_description,
                targetConfiguration=target_configuration,
                credentialProviderConfigurations=credential_provider_configurations
            )
            return response
        except ClientError as e:
            logging.error(f"Error updating agent gateway: {e}")
            raise e

@click.command()
@click.option("--action", required=True, default="invoke", help="Action to perform")
@click.option("--gateway-name", help="Gateway name")
@click.option("--gateway-id", help="Gateway ID")
@click.option("--gateway-description", help="Gateway description")
@click.option("--execution-role", help="Execution role")
@click.option("--authorizer-configuration", help="Authorizer configuration")
@click.option("--target-name", help="Target name")
@click.option("--target-id", help="Target ID")
@click.option("--target-description", help="Target description")
@click.option("--openapi-file", help="OpenAPI file")
@click.option("--credential-provider-inputs", help="Credential provider inputs")
def main(action,
    gateway_name,
    gateway_id,
    gateway_description,
    execution_role,
    authorizer_configuration,
    target_name,
    target_id,
    target_description,
    openapi_file,
    credential_provider_inputs
):
    agentcore_gateway = AgentCoreGateway()
    debug_vars = {
        "action": action,
        "gateway_name": gateway_name,
        "gateway_id": gateway_id,
        "gateway_description": gateway_description,
        "execution_role": execution_role,
        "authorizer_configuration": authorizer_configuration,
        "target_name": target_name,
        "target_id": target_id,
        "target_description": target_description,
        "openapi_file": openapi_file,
        "credential_provider_inputs": credential_provider_inputs,
    }
    logging.debug(json.dumps(debug_vars, indent=4, cls=DateTimeEncoder))
    match action:
        case "gateway.create":
            authorizer_configuration = json.loads(authorizer_configuration) if authorizer_configuration else None
            response = agentcore_gateway.create_gateway(gateway_name, gateway_description, execution_role, authorizer_configuration)
            logging.info(json.dumps(response, cls=DateTimeEncoder))
        case "gateway.update":
            authorizer_configuration = json.loads(authorizer_configuration) if authorizer_configuration else None
            response = agentcore_gateway.update_gateway(gateway_id, gateway_name, gateway_description, execution_role, authorizer_configuration)
            logging.info(json.dumps(response, cls=DateTimeEncoder))
        case "target.create":
            credential_provider_inputs = json.loads(credential_provider_inputs) if credential_provider_inputs else None
            response = agentcore_gateway.create_gateway_target(gateway_id, target_name, target_description, openapi_file, credential_provider_inputs)
            logging.info(json.dumps(response, cls=DateTimeEncoder))
        case "target.update":
            credential_provider_inputs = json.loads(credential_provider_inputs) if credential_provider_inputs else None
            response = agentcore_gateway.update_gateway_target(gateway_id, target_id, target_name, target_description, openapi_file, credential_provider_inputs)
            logging.info(json.dumps(response, cls=DateTimeEncoder))
        case _:
            logging.info(json.dumps({"message": f"invalid action: {action}"}))

if __name__ == "__main__":
    main()
