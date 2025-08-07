# Agents

This repository contains an example implementation of a Strands agent deployed on Amazon Bedrock AgentCore.

## Project Structure

```
agents/
├── README.md                           # This file
└── strands-on-agentcore/               # Strands Agents on Bedrock AgentCore
    ├── Dockerfile                      # Container configuration
    ├── pyproject.toml                  # Python project configuration
    ├── requirements.txt                # Python dependencies
    ├── src/
    │   └── agent.py                    # Main agent implementation
    ├── iac/                            # Infrastructure as Code
    │   ├── deploy.py                   # Deployment script
    │   ├── infrastructure.yaml         # Infrastructure configuration
    │   └── infrastructure_output.yaml  # Generated infrastructure output
    └── etc/                            # Additional configuration files
```

### Quick Start

1. **Prerequisites**
   - Python 3.12+
   - Docker
   - AWS CLI configured
   - Appropriate AWS permissions for Bedrock services

2. **Local Development**
   ```bash
   cd strands-on-agentcore
   uv pip install -r requirements.txt
   make local.agent
   ```

3. **Docker Deployment**
   ```bash
   cd strands-on-agentcore
   make podman.build
   make local.podman
   ```

4. **AWS Deployment**
   ```bash
   cd strands-on-agentcore/iac
   uv run deploy.py
   ```

### Configuration

The agent can be configured through environment variables. The project includes a template file that should be copied and customized:

1. **Setup Environment Configuration**
   ```bash
   cd strands-on-agentcore
   cp etc/environment.template etc/environment.sh
   # edit etc/environment.sh with your specific values
   ```

2. **Key Configuration Variables**
   - `PROFILE`: Your AWS CLI profile name
   - `REGION`: AWS region for Bedrock services (default: "us-east-1")
   - `BUCKET`: S3 bucket for deployment artifacts
   - `ACCOUNTID`: Your AWS account ID

   **Infrastructure Configuration:**
   - `P_REPOSITORY_NAME`: ECR repository name for the agent

   **Container Configuration:**
   - `C_VERSION`: Container version tag, which should be incremented for each deployment

   **Agent Configuration:**
   - `O_AGENT_ARN`: Output agent runtime ARN (populated after deployment)
   - `O_AGENT_VERSION`: Output agent runtime version (populated after deployment)

   **Platform Configuration:**
   - `PLATFORM_DEPLOY`: Target platform for deployment (linux/amd64 or linux/arm64)
   - `PLATFORM_LOCAL`: Local platform for development (linux/amd64 or linux/arm64)

   **OpenTelemetry Configuration:**
   - `OTEL_METRICS_EXPORTER`: Metrics exporter configuration
   - `OTEL_TRACES_EXPORTER`: Traces exporter configuration
   - `OTEL_LOGS_EXPORTER`: Logs exporter configuration
   - `OTEL_RESOURCE_DETECTORS`: Resource detection configuration
