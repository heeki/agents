# A2A Multi-Agent Fitness System

An AI-powered workout planning system demonstrating multi-agent collaboration using the **Google A2A Protocol** with three specialized agents deployed on **Amazon Bedrock AgentCore Runtime**.

## Overview

**Momentum Fitness** is a modern dark-themed Streamlit application that coordinates three AI agents to create personalized workout plans that balance physiological optimization with real-world constraints (time, equipment, schedule).

### The Three Agents

| Agent | Framework | Role | Expertise |
|-------|-----------|------|-----------|
| **Orchestrator** | Strands SDK (Python) | Central coordinator ("Head Coach") | Workflow coordination, conflict resolution |
| **Biomechanics Lab** | LangGraph (TypeScript) | Exercise physiologist | Optimal workout design, exercise selection |
| **Life Sync** | LangGraph (Python) | Logistics coordinator | Schedule validation, equipment availability |

### Why A2A Protocol Matters

The **Google A2A (Agent-to-Agent) Protocol** enables heterogeneous agent frameworks to communicate via a standard interface:

- **Interoperability**: Strands SDK and LangGraph agents work together seamlessly
- **Standardization**: JSON-RPC based protocol with agent cards, task submission, streaming
- **Portability**: Same agent code runs locally (Docker Compose) and deployed (AgentCore)
- **Flexibility**: Multiple transport options (HTTP, AWS SDK) with consistent A2A messaging

---

## Architecture

### System Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                    MOMENTUM FITNESS FRONTEND                         │
│                         (Streamlit - Dark Theme)                     │
│             User: "Build me a strength workout"                      │
└──────────────────────────────────────────────────────────────────────┘
                                    │
                   boto3.client("bedrock-agentcore")
                   invoke_agent_runtime(agentRuntimeArn=...)
                   AWS SDK call with SigV4 auth
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────┐
│               AWS BEDROCK AGENTCORE RUNTIME                          │
│               ProtocolConfiguration: A2A                             │
│          (AgentCore forwards to container via A2A)                   │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                    AGENT 1: ORCHESTRATOR                       │  │
│  │                    (Strands Agents SDK - Python)               │  │
│  │                                                                │  │
│  │  Workflow:                                                     │  │
│  │  1. Parse user request                                         │  │
│  │  2. Call Biomechanics Lab → get optimal workout                │  │
│  │  3. Call Life Sync → validate constraints                      │  │
│  │  4. If conflicts → request refinement                          │  │
│  │  5. Return final validated plan                                │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                          │                   │                       │
│      (A2A via boto3/HTTP)│                   │  (A2A via boto3/HTTP) │
│                          ▼                   ▼                       │
│  ┌─────────────────────────────────┐ ┌─────────────────────────────┐ │
│  │   AGENT 2: BIOMECHANICS LAB     │ │   AGENT 3: LIFE SYNC AGENT  │ │
│  │   (LangGraph SDK - TypeScript)  │ │   (LangGraph SDK - Python)  │ │
│  │                                 │ │                             │ │
│  │  Tools:                         │ │  Tools:                     │ │
│  │  - SearchExercises              │ │  - GetCalendarAvailability  │ │
│  │                                 │ │  - GetEquipmentInventory    │ │
│  │                                 │ │                             │ │
│  │  Returns: JSON workout plan     │ │  Returns: Conflict analysis │ │
│  └─────────────────────────────────┘ └─────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Request Workflow

Understanding how requests flow through the system is critical. This section documents each hop in detail.

### Hop 1: Frontend → Orchestrator (AWS SDK)

**Component**: `frontend/app.py:send_workout_request()`

**The frontend uses AWS SDK (boto3), NOT direct HTTP/A2A calls:**

```python
import boto3
import json

# Initialize boto3 client with service name "bedrock-agentcore"
client = boto3.client("bedrock-agentcore", region_name="us-east-1")

# Prepare A2A-style payload
request_payload = {
    "jsonrpc": "2.0",
    "id": "workout-123",
    "method": "tasks/send",
    "params": {
        "task": {
            "id": "workout-123",
            "message": {
                "role": "user",
                "parts": [{"type": "text", "text": "Build me a strength workout"}]
            }
        }
    }
}

# Invoke via AWS SDK (NOT HTTP)
response = client.invoke_agent_runtime(
    agentRuntimeArn="arn:aws:bedrock-agentcore:...",
    qualifier="DEFAULT",
    contentType="application/json",
    accept="application/json",
    payload=json.dumps(request_payload)
)
```

**Key Points**:
- **Transport**: AWS SDK (boto3) with service name `bedrock-agentcore`
- **Method**: `invoke_agent_runtime()` - this is an AWS API call, not HTTP/A2A
- **Auth**: SigV4 (via AWS profile/credentials)
- **Payload**: A2A JSON-RPC wrapped in AWS API format
- **Location**: `frontend/app.py` lines 220-227

### Hop 2: AgentCore → Orchestrator Container (Internal)

**Component**: AWS AgentCore Runtime

- **Transport**: Internal (AgentCore runtime mechanism)
- **Protocol**: A2A JSON-RPC
- **Auth**: Managed by AgentCore
- **Payload**: Pure A2A JSON-RPC message
- **Process**: AgentCore extracts the A2A payload from the AWS API call and forwards it to the orchestrator container's A2A endpoint

This is where the transition happens: AWS API call → A2A protocol.

### Hop 3: Orchestrator → Sub-agents (A2A with Auto-Detection)

**Component**: `agents/orchestrator/a2a/client.py:A2AClient`

The `A2AClient` automatically detects whether to use boto3 or HTTP based on the environment variable value:

```python
def _is_arn(value: str) -> bool:
    """Check if a string is an AWS ARN."""
    return value.startswith("arn:aws:")

class A2AClient:
    def __init__(self, agent_url: str, agent_name: str, ...):
        self.agent_url = agent_url.rstrip("/")
        self._use_agentcore = _is_arn(agent_url)

        if self._use_agentcore:
            # Use boto3 for ARN-based invocations
            import boto3
            region = os.getenv("AWS_REGION", "us-east-1")
            self._boto_client = boto3.client("bedrock-agentcore", region_name=region)
        # Otherwise use HTTP client (httpx)
```

**Transport Options**:
- **If ARN** (`BIOMECHANICS_ARN` set): Uses `boto3.client("bedrock-agentcore")`
- **If URL** (`BIOMECHANICS_URL` set): Uses `httpx` HTTP client

**Protocol**: A2A JSON-RPC (both transports)
**Auth**: Execution role (boto3) or none (local HTTP)
**Payload**: A2A `tasks/send` messages
**Location**: `agents/orchestrator/a2a/client.py` lines 26-81

**Important**: Both transport methods use the same A2A protocol format. The difference is only in the network layer.

---

## Deployment

### Prerequisites

- **Python 3.12+**
- **Node.js 22+**
- **Podman Desktop** (or Docker)
- **AWS CLI** configured with credentials
- **uv** for Python dependency management: `pip install uv`
- **podman-compose**: `pip install podman-compose`

### Build and Push Containers

```bash
# Deploy AWS infrastructure (ECR, IAM, Security Groups)
make infrastructure

# Build all container images (ARM64)
make build.all

# Push to ECR
make push.all
```

### Deploy to AgentCore

```bash
# Deploy all three agents to Amazon Bedrock AgentCore
make deploy.all

# Or deploy individually
make orchestrator.deploy
make biomechanics.deploy
make lifesync.deploy
```

### Verify Deployment

```bash
# List deployed runtimes
source .venv-iac/bin/activate
python iac/deploy.py --action list
```

Expected output:
```
Runtime: a2a_orchestrator-UvVptn34jn
  Status: READY
  Version: 1
  ARN: arn:aws:bedrock-agentcore:us-east-1:...:runtime/a2a_orchestrator-UvVptn34jn
```

### Update Environment Variables

After deployment, update `etc/environment.sh` with the runtime ARNs:

```bash
# Runtime ARNs (for boto3 transport - recommended for production)
export ORCHESTRATOR_RUNTIME_ARN="arn:aws:bedrock-agentcore:us-east-1:...:runtime/a2a_orchestrator-..."
export BIOMECHANICS_RUNTIME_ARN="arn:aws:bedrock-agentcore:us-east-1:...:runtime/a2a_biomechanics_lab-..."
export LIFESYNC_RUNTIME_ARN="arn:aws:bedrock-agentcore:us-east-1:...:runtime/a2a_life_sync-..."
```

---

## Local Development

### Option 1: Docker Compose (Recommended)

Run all three agents in containers:

```bash
# Build images
make local.compose.build

# Start all agents
make local.compose.up

# Or build and start in one command
make local.compose.up.build

# View logs
make local.compose.logs

# Check status
make local.compose.ps

# Stop agents
make local.compose.down
```

**Exposed Ports**:
- Orchestrator: `http://localhost:8081`
- Biomechanics Lab: `http://localhost:8082`
- Life Sync: `http://localhost:8083`

### Option 2: Run Agents Individually (No Containers)

```bash
# Terminal 1: Orchestrator
make local.orchestrator

# Terminal 2: Biomechanics Lab
make local.biomechanics

# Terminal 3: Life Sync
make local.lifesync
```

### Test Local Agents

```bash
# Check agent cards
curl http://localhost:8081/.well-known/agent.json | jq
curl http://localhost:8082/.well-known/agent.json | jq
curl http://localhost:8083/.well-known/agent.json | jq

# Send a workout request
make invoke.simple

# Test conflict scenario
make invoke.conflict
```

---

## Frontend

### Momentum Fitness UI

A modern dark-themed Streamlit application inspired by contemporary design trends.

**Features**:
- Interactive workout builder with form inputs
- Custom prompt interface for freeform requests
- Real-time agent status display (Orchestrator, Biomechanics Lab, Life Sync)
- Observability logs showing inter-agent communication
- Dark theme with gradient accents and clean typography

### Running the Frontend

```bash
# Configure environment
cd frontend
cp .env.example .env  # If .env doesn't exist

# Edit .env with your configuration:
# - For deployed: ORCHESTRATOR_RUNTIME_ARN=arn:aws:bedrock-agentcore:...
# - For local: ORCHESTRATOR_URL=http://localhost:8081

# Run frontend
make frontend.run
# Or: cd frontend && uv run streamlit run app.py
```

Open browser: **http://localhost:8501**

### Frontend Configuration

**`.env` file**:

```bash
# For deployed agents (AWS SDK - Production)
ORCHESTRATOR_RUNTIME_ARN=arn:aws:bedrock-agentcore:us-east-1:...:runtime/a2a_orchestrator-...
BIOMECHANICS_RUNTIME_ARN=arn:aws:bedrock-agentcore:us-east-1:...:runtime/a2a_biomechanics_lab-...
LIFESYNC_RUNTIME_ARN=arn:aws:bedrock-agentcore:us-east-1:...:runtime/a2a_life_sync-...
AWS_REGION=us-east-1
AWS_PROFILE=your-profile-name

# For local agents (HTTP - Development)
ORCHESTRATOR_URL=http://localhost:8081
BIOMECHANICS_URL=http://localhost:8082
LIFESYNC_URL=http://localhost:8083
```

**Auto-detection**: Frontend checks if `ORCHESTRATOR_RUNTIME_ARN` is set to determine whether to use boto3 SDK or HTTP.

---

## Testing

### Unit Tests

Each agent has isolated unit tests:

```bash
# Orchestrator
cd agents/orchestrator
uv run pytest tests/

# Biomechanics Lab
cd agents/biomechanics-lab
npm test

# Life Sync
cd agents/life-sync
uv run pytest tests/
```

### Integration Tests

End-to-end A2A protocol validation:

```bash
# Requires Docker Compose to be running
make local.compose.up

# Run integration tests
make test.integration
```

**Test Scenarios**:
1. **Happy Path**: User requests hypertrophy workout → Biomechanics Lab returns plan → Life Sync confirms availability → Orchestrator returns plan
2. **Time Conflict**: Life Sync reports 30-minute gap → Orchestrator requests refinement → Biomechanics Lab returns shorter workout
3. **Equipment Conflict**: Life Sync reports no barbell → Orchestrator requests bodyweight alternatives
4. **Sub-Agent Failure**: Biomechanics Lab unavailable → Retry 3x → Return error

---

## Configuration

### Environment Variables

All configuration is managed in `etc/environment.sh`:

```bash
# AWS Configuration
export AWS_REGION="us-east-1"
export AWS_PROFILE="your-profile-name"
export AWS_ACCOUNT_ID="123456789012"

# Model Configuration
export MODEL_ID="us.amazon.nova-lite-v1:0"

# ECR Repositories
export ECR_ORCHESTRATOR_URI="123456789012.dkr.ecr.us-east-1.amazonaws.com/a2a/a2a-orchestrator"
export ECR_BIOMECHANICS_URI="123456789012.dkr.ecr.us-east-1.amazonaws.com/a2a/a2a-biomechanics-lab"
export ECR_LIFESYNC_URI="123456789012.dkr.ecr.us-east-1.amazonaws.com/a2a/a2a-life-sync"

# AgentCore Runtimes (set after deployment)
export ORCHESTRATOR_RUNTIME_ID="a2a_orchestrator-UvVptn34jn"
export ORCHESTRATOR_RUNTIME_ARN="arn:aws:bedrock-agentcore:us-east-1:...:runtime/a2a_orchestrator-..."
export BIOMECHANICS_RUNTIME_ID="a2a_biomechanics_lab-qhEyyzCGxm"
export BIOMECHANICS_RUNTIME_ARN="arn:aws:bedrock-agentcore:us-east-1:...:runtime/a2a_biomechanics_lab-..."
export LIFESYNC_RUNTIME_ID="a2a_life_sync-VLvant9rg7"
export LIFESYNC_RUNTIME_ARN="arn:aws:bedrock-agentcore:us-east-1:...:runtime/a2a_life_sync-..."

# IAM and Networking
export EXECUTION_ROLE_ARN="arn:aws:iam::123456789012:role/a2a-fitness-agent-role"
export SECURITY_GROUP_ID="sg-0a7f79544b9969e8f"
```

### Source Configuration

```bash
source etc/environment.sh
```

---

## Makefile Targets

### Infrastructure

```bash
make infrastructure          # Deploy ECR, IAM, Security Groups
make cognito                 # Deploy Cognito User Pool (optional)
make apigw                   # Deploy API Gateway (optional)
```

### Build & Deploy

```bash
make build.all               # Build all containers (ARM64)
make push.all                # Push all to ECR
make deploy.all              # Deploy all to AgentCore

# Individual agents
make orchestrator.build      # Build Orchestrator container
make orchestrator.push       # Push to ECR
make orchestrator.deploy     # Deploy to AgentCore
```

### Local Development

```bash
make local.compose.build     # Build images
make local.compose.up        # Start all agents via Docker Compose
make local.compose.up.build  # Build and start in one command
make local.compose.down      # Stop all agents
make local.compose.logs      # Follow logs
make local.compose.ps        # Show running containers
make local.compose.restart   # Restart all agents

# Run individually (no containers)
make local.orchestrator      # Run Orchestrator locally
make local.biomechanics      # Run Biomechanics Lab locally
make local.lifesync          # Run Life Sync locally
```

### Testing

```bash
make test.unit               # Run all unit tests
make test.integration        # Run integration tests
```

### Frontend

```bash
make frontend.run            # Run Streamlit frontend
```

### Invocation

```bash
make invoke.simple           # Test simple request
make invoke.conflict         # Test conflict scenario
make invoke.agentcard        # View Orchestrator agent card
```

---

## Project Structure

```
a2a-with-agentcore/
├── CLAUDE.md                          # Project steering
├── SPECIFICATION.md                   # Technical specification
├── README.md                          # This document
├── makefile                           # Root orchestration
├── etc/
│   └── environment.sh                 # Configuration injection
├── agents/
│   ├── orchestrator/                  # Agent 1: Strands (Python)
│   │   ├── app.py                     # Main application
│   │   ├── a2a/
│   │   │   ├── server.py              # A2A JSON-RPC server
│   │   │   ├── client.py              # A2A client with auto-detection
│   │   │   └── types.py               # A2A type definitions
│   │   ├── tools/
│   │   │   └── a2a_tools.py           # Strands tools wrapping A2A client
│   │   ├── tests/
│   │   ├── requirements.txt
│   │   ├── dockerfile
│   │   └── pyproject.toml
│   │
│   ├── biomechanics-lab/              # Agent 2: LangGraph (TypeScript)
│   │   ├── src/
│   │   │   ├── index.ts               # Main entry point
│   │   │   ├── agent.ts               # LangGraph agent definition
│   │   │   ├── a2a/
│   │   │   │   ├── server.ts          # A2A JSON-RPC server
│   │   │   │   └── types.ts           # A2A type definitions
│   │   │   └── tools/
│   │   │       └── searchExercises.ts # Mock exercise search tool
│   │   ├── tests/
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   └── dockerfile
│   │
│   └── life-sync/                     # Agent 3: LangGraph (Python)
│       ├── src/
│       │   ├── app.py                 # Main entry point
│       │   ├── agent.py               # LangGraph agent definition
│       │   ├── a2a/
│       │   │   ├── server.py          # A2A JSON-RPC server
│       │   │   └── types.py           # A2A type definitions
│       │   └── tools/
│       │       ├── calendar.py        # Mock calendar tool
│       │       └── equipment.py       # Mock equipment tool
│       ├── tests/
│       ├── requirements.txt
│       ├── dockerfile
│       └── pyproject.toml
│
├── frontend/
│   ├── app.py                         # Momentum Fitness Streamlit frontend
│   ├── requirements.txt
│   └── .env                           # Frontend configuration
│
├── iac/
│   ├── infrastructure.yaml            # ECR repos, IAM roles, Security Groups
│   ├── cognito.yaml                   # Cognito User Pool (optional)
│   ├── apigw.yaml                     # API Gateway (optional)
│   ├── agentcore.yaml                 # AgentCore runtimes (A2A protocol)
│   └── deploy.py                      # AgentCore deployment helper
│
├── docker/
│   └── docker-compose.yaml            # Local development setup
│
└── tests/
    └── integration/
        └── test_a2a_flow.py           # End-to-end A2A integration tests
```

---

## Performance

### Response Times

- **Cold Start** (first request): 10-30 seconds
  - Container initialization in AgentCore
  - Model loading
  - Initial connection setup

- **Warm Request** (subsequent): 2-5 seconds
  - Container already running
  - Model cached
  - Established connections

### Optimizations

1. **AgentCore keeps containers warm** between requests
2. **Boto3 session caching** (no repeated authentication)
3. **Frontend shows loading spinner** during processing
4. **Streaming responses** for real-time feedback (future enhancement)

---

## Security

### AWS Credentials Flow

```
Frontend (uses AWS Profile credentials)
    ↓ boto3.client("bedrock-agentcore")
AgentCore (validates IAM permissions)
    ↓ Assumes Execution Role
Agent Containers (arn:aws:iam::...:role/a2a-fitness-agent-role)
    ↓ Bedrock API calls
Amazon Nova Lite Model
```

### Security Layers

1. **Frontend**: AWS credentials via IAM profile (local dev) or IAM role (production)
2. **AgentCore**: IAM role-based access control
3. **Agents**: Execution role with least-privilege permissions
4. **Model**: Bedrock service permissions
5. **Inter-agent**: Execution role credentials (boto3) or none (local HTTP)

### IAM Permissions

**AgentCore Execution Role** requires:
- `ecr:GetAuthorizationToken`, `ecr:BatchCheckLayerAvailability`, `ecr:GetDownloadUrlForLayer`, `ecr:BatchGetImage`
- `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`
- `xray:PutTraceSegments`, `xray:PutTelemetryRecords`
- `bedrock:InvokeModelWithResponseStream`
- `bedrock-agentcore:InvokeAgentRuntime` (for inter-agent A2A calls)

---

## Monitoring & Observability

### CloudWatch Logs

```bash
# AgentCore Runtime Logs
Log Group: /aws/bedrock/agentcore/runtime/a2a_orchestrator-UvVptn34jn
Log Group: /aws/bedrock/agentcore/runtime/a2a_biomechanics_lab-qhEyyzCGxm
Log Group: /aws/bedrock/agentcore/runtime/a2a_life_sync-VLvant9rg7
```

### Frontend Observability

The Momentum Fitness UI includes a dedicated "Observability" section showing:
- **Active Agents**: Real-time status of all three agents
- **Request Flow**: Visual trace of Frontend → Orchestrator → Sub-agents
- **Logs**: Captured inter-agent communication for debugging

### Local Monitoring

```bash
# Docker Compose logs
make local.compose.logs

# Or follow specific agent
podman-compose logs -f orchestrator
podman-compose logs -f biomechanics-lab
podman-compose logs -f life-sync
```

---

## Cost Considerations

### Active Resources

- **3 AgentCore runtimes** (pay per request and compute time)
- **3 ECR repositories** (minimal storage cost)
- **1 IAM role** (no charge)
- **1 Security group** (no charge)

### Cost Optimization

- Use **local agents** for development and testing
- **Delete unused runtimes** when not needed
- Monitor **CloudWatch metrics** for usage patterns
- Use **ARM64 containers** (cost optimized vs x86)

### Delete Resources

```bash
# Delete runtimes
source .venv-iac/bin/activate
python iac/deploy.py --action delete --runtime-id <runtime-id>

# Delete infrastructure stack
make infrastructure.delete
```

---

## Troubleshooting

### Frontend Can't Connect

```bash
# For local agents
curl http://localhost:8081/health

# For deployed agents
aws sts get-caller-identity --profile your-profile-name
```

### Slow Responses

- **First request**: Cold start is normal (10-30s)
- **All requests slow**: Check CloudWatch logs for errors
- **Timeouts**: Verify agent status with `python iac/deploy.py --action list`

### Agent Errors

```bash
# Check CloudWatch logs
aws logs tail /aws/bedrock/agentcore/runtime/a2a_orchestrator-... --follow

# Check local logs
make local.compose.logs
```

### Docker Compose Issues

```bash
# Rebuild images
make local.compose.build

# Reset everything
make local.compose.down
podman system prune -af
make local.compose.up.build
```

---

## Platform Notes

- **Apple Silicon Macs (M1/M2/M3)**: Native ARM64 - optimal performance
- **Intel Macs**: Uses QEMU emulation for ARM64 containers (slower but functional)
- **Linux**: Native support for both ARM64 and x86_64
- **Windows**: Use WSL2 with Docker or Podman

**AgentCore Deployment**: Requires ARM64 architecture for cost optimization

---

## License

MIT

---

## Additional Documentation

- **SPECIFICATION.md**: Detailed technical specification with A2A protocol implementation details
- **CLAUDE.md**: Project steering and coding standards

---

**Last Updated**: February 6, 2026
**AWS Region**: us-east-1
