# A2A Multi-Agent Fitness System Specification

## Overview

A multi-agent collaboration system using the **Google A2A Protocol** across three agents deployed in **Amazon Bedrock AgentCore Runtime**. The system demonstrates how heterogeneous agent frameworks (Strands SDK, LangGraph) can interoperate via the A2A standard.

### Architecture Principle: A2A for Inter-Agent Communication

This system demonstrates multi-agent collaboration using the **Google A2A Protocol** with a hybrid transport approach that distinguishes between frontend-to-orchestrator and inter-agent communication:

- **Frontend → Orchestrator**: Uses AWS SDK (`boto3` with service name `bedrock-agentcore`) to invoke the orchestrator agent via `invoke_agent_runtime(agentRuntimeArn=..., payload=...)`. This is an AWS API call with SigV4 authentication, not a direct HTTP/A2A call.
- **AgentCore natively supports A2A** via `ProtocolConfiguration: A2A`. AgentCore receives the AWS SDK request and forwards it to the orchestrator container using the A2A protocol internally.
- **Inter-agent communication uses A2A**: The orchestrator calls sub-agents (Biomechanics Lab and Life Sync) using the A2A protocol. The `A2AClient` in `agents/orchestrator/a2a/client.py` automatically detects whether to use boto3 (for ARNs) or HTTP (for URLs).
- **Agent code is portable** between local and deployed environments. The same container image runs in Docker Compose locally and in AgentCore, with only environment variable differences (URLs vs ARNs).

### Architecture Summary

```
┌──────────────────────────────────────────────────────────────────────┐
│                    MOMENTUM FITNESS FRONTEND                         │
│                         (Streamlit - Dark Theme)                     │
│                    "Build me a strength workout"                     │
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
│  │  Role: Central coordinator ("Head Coach")                      │  │
│  │  Model: Amazon Nova Lite                                       │  │
│  │                                                                │  │
│  │  A2A Flow:                                                     │  │
│  │  1. Receive user goal via AgentCore A2A interface              │  │
│  │  2. Call Biomechanics Lab via A2A (boto3 or HTTP)              │  │
│  │  3. Call Life Sync Agent via A2A (boto3 or HTTP)               │  │
│  │  4. If conflict → request refinement from Biomechanics Lab     │  │
│  │  5. Return final plan to user via A2A response                 │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                          │                   │                       │
│      (A2A via boto3/HTTP)│                   │  (A2A via boto3/HTTP) │
│                          ▼                   ▼                       │
│  ┌─────────────────────────────────┐ ┌─────────────────────────────┐ │
│  │   AGENT 2: BIOMECHANICS LAB     │ │   AGENT 3: LIFE SYNC AGENT  │ │
│  │   (LangGraph SDK - TypeScript)  │ │   (LangGraph SDK - Python)  │ │
│  │                                 │ │                             │ │
│  │  Role: Exercise physiology      │ │  Role: Logistics            │ │
│  │  Model: Amazon Nova Lite        │ │  Model: Amazon Nova Lite    │ │ 
│  │                                 │ │                             │ │
│  │  Tools:                         │ │  Tools:                     │ │
│  │  - SearchExercises (mocked)     │ │  - GetCalendarAvailability  │ │
│  │                                 │ │  - GetEquipmentInventory    │ │
│  │                                 │ │                             │ │
│  │  Returns: JSON workout plan     │ │  Returns: Conflict analysis │ │
│  └─────────────────────────────────┘ └─────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Local vs. Deployed Environments

The same agent code runs in both environments. The only differences are URL values and authentication.

### Local (Docker Compose)

```
Client ──HTTP A2A──► Orchestrator (:8081) ──HTTP A2A──► Biomechanics Lab (:8082)
                                           ──HTTP A2A──► Life Sync (:8083)
```

- Plain HTTP, no authentication
- URLs are `http://localhost:<port>` or Docker Compose service names
- Environment variables: `BIOMECHANICS_URL=http://biomechanics-lab:8082`

### Deployed (AgentCore)

```
Frontend ──boto3 SDK──► AgentCore ──A2A──► Orchestrator ──A2A (boto3 or HTTP)──► Sub-agents
```

- Frontend uses `boto3.client("bedrock-agentcore").invoke_agent_runtime(agentRuntimeArn=...)` with SigV4 auth
- AgentCore receives AWS API call and forwards to orchestrator container via A2A protocol
- Orchestrator calls sub-agents using `A2AClient` which auto-detects ARN vs URL
  - If ARN: Uses boto3 bedrock-agentcore client
  - If URL: Uses HTTP/A2A
- Environment variables: `BIOMECHANICS_ARN=<agent-arn>` or `BIOMECHANICS_URL=<http-url>`

### What Differs

| Aspect | Local | Deployed |
|--------|-------|----------|
| Agent code | Identical | Identical |
| Container image | Same | Same |
| Sub-agent URLs | `http://service:port` | AgentCore A2A endpoint |
| External client auth | None | SigV4 |
| Inter-agent auth | None | Execution role credentials |

### Frontend Integration

The **Momentum Fitness** Streamlit frontend (`frontend/app.py`) uses AWS SDK to invoke the orchestrator:

```python
import boto3
import json

# Initialize boto3 client
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

# Invoke via AWS SDK (not HTTP)
response = client.invoke_agent_runtime(
    agentRuntimeArn="arn:aws:bedrock-agentcore:...",
    qualifier="DEFAULT",
    contentType="application/json",
    accept="application/json",
    payload=json.dumps(request_payload)
)
```

This is **not a direct A2A HTTP call** — it's an AWS SDK call that wraps the A2A payload. AgentCore handles the protocol conversion internally.

---

## Decision Summary

| Category | Decision |
|----------|----------|
| A2A Protocol | Google A2A Protocol Spec with Streaming |
| A2A Features | Agent Cards, Tasks (send/get), SSE Streaming |
| Agent Protocol | A2A only — no `/invocations` or SDK-level wrappers |
| Tools | Fully Mocked (static/random data) |
| Entry Point | AgentCore A2A endpoint (SigV4 auth) |
| Authentication (external) | SigV4 (direct) or Cognito JWT (via API Gateway) |
| Authentication (inter-agent) | Execution role credentials |
| Model | Amazon Nova Lite (`us.amazon.nova-lite-v1:0`) |
| State Management | Stateless (no persistence) |
| Infrastructure | New dedicated resources |
| Error Handling | Retry with exponential backoff (3 attempts) |
| Testing | Unit tests + Local Docker Compose |

---

## A2A Protocol Implementation

### Agent Card (/.well-known/agent.json)

Each agent exposes an Agent Card at `/.well-known/agent.json`:

```json
{
  "name": "orchestrator",
  "description": "Central coordinator for fitness multi-agent system",
  "url": "https://orchestrator.agentcore.example.com",
  "version": "1.0.0",
  "capabilities": {
    "streaming": true,
    "pushNotifications": false
  },
  "skills": [
    {
      "id": "create-workout",
      "name": "Create Workout Plan",
      "description": "Creates a personalized workout plan considering user goals and constraints"
    }
  ]
}
```

### A2A JSON-RPC Endpoints

Each agent implements the following A2A JSON-RPC methods:

| Method | Description |
|--------|-------------|
| `tasks/send` | Submit a new task to the agent |
| `tasks/get` | Retrieve task status and result |
| `tasks/cancel` | Cancel a running task |
| `tasks/sendSubscribe` | Submit task and subscribe to SSE updates |

These are the **only** endpoints an agent exposes (along with health checks). There is no `/invocations` or other non-A2A endpoint.

### HTTP Endpoints Per Agent

| Path | Method | Purpose |
|------|--------|---------|
| `/` | POST | A2A JSON-RPC handler (primary) |
| `/.well-known/agent.json` | GET | Agent Card for A2A discovery |
| `/health` | GET | Health check |

The root `POST /` endpoint handles all A2A JSON-RPC methods (`tasks/send`, `tasks/get`, `tasks/cancel`, `tasks/sendSubscribe`) by dispatching on the `method` field in the JSON-RPC request body.

### Message Format

```json
{
  "jsonrpc": "2.0",
  "id": "task-123",
  "method": "tasks/send",
  "params": {
    "task": {
      "id": "task-123",
      "message": {
        "role": "user",
        "parts": [
          {
            "type": "text",
            "text": "Create a hypertrophy workout for upper body"
          }
        ]
      }
    }
  }
}
```

### Streaming (SSE)

For `tasks/sendSubscribe`, responses are streamed via Server-Sent Events:

```
event: task-status
data: {"taskId": "task-123", "status": "working", "message": "Analyzing goal..."}

event: task-status
data: {"taskId": "task-123", "status": "working", "message": "Generating exercises..."}

event: task-result
data: {"taskId": "task-123", "status": "completed", "result": {...}}
```

---

## Agent Specifications

### Agent 1: Orchestrator ("Head Coach")

**Framework**: Strands Agents SDK (Python)

**System Prompt**:
```
You are the central coordinator for a fitness multi-agent system.

Objective: Translate high-level user goals into actionable instructions for
sub-agents and resolve conflicts between "ideal training" and "life reality."

A2A Logic:
1. Call the Biomechanics Lab to get the physiologically optimal workout.
2. Call the Life Sync Agent to check calendar availability and equipment.
3. If Life Sync reports a conflict (e.g., "no time" or "no gym access"),
   send a refinement request to Biomechanics Lab to adjust the workout
   (e.g., "convert to 20-min bodyweight session").
4. Return the final, validated workout plan to the user.

Tone: Professional, decisive, and results-oriented.
```

**A2A Client Tools**:
- `call_biomechanics_lab(goal: str, constraints: dict | None) -> WorkoutPlan`
- `call_life_sync_agent(workout_plan: WorkoutPlan) -> ConstraintAnalysis`

All tools use a single `A2AClient` (`agents/orchestrator/a2a/client.py`) that automatically detects the transport method:
- **ARN Detection**: If environment variable value starts with `arn:aws:`, uses `boto3.client("bedrock-agentcore")`
- **URL Detection**: If environment variable is an HTTP URL, uses `httpx` for direct A2A calls
- Environment variables: `BIOMECHANICS_ARN` or `BIOMECHANICS_URL`, `LIFESYNC_ARN` or `LIFESYNC_URL`

**Response Format**: Natural language summary with structured workout JSON

---

### Agent 2: Biomechanics Lab (Sub-Agent A)

**Framework**: LangGraph SDK (TypeScript)

**System Prompt**:
```
You are an expert in exercise physiology and strength & conditioning.

Objective: Provide structured workout routines based on specific physiological
goals (hypertrophy, endurance, power).

A2A Logic:
- Receive a goal from the Orchestrator
- Return a JSON array of exercises, sets, and reps
- If the Orchestrator asks for a "compromise," prioritize intensity over
  duration to maintain the training stimulus

Tone: Clinical, data-driven, and technical.
```

**Tools**:
- `searchExercises(params: SearchParams) -> Exercise[]`

**Mock Tool Implementation** (SearchExercises):
```typescript
interface SearchParams {
  muscleGroup?: string;
  equipment?: string[];
  difficulty?: "beginner" | "intermediate" | "advanced";
  goalType?: "hypertrophy" | "strength" | "endurance" | "power";
}

interface Exercise {
  id: string;
  name: string;
  muscleGroup: string;
  equipment: string[];
  sets: number;
  reps: string; // e.g., "8-12" or "5"
  restSeconds: number;
  notes?: string;
}
```

**Response Format**:
```json
{
  "workout": {
    "name": "Upper Body Hypertrophy",
    "estimatedDuration": 45,
    "exercises": [
      {
        "id": "bench-press-001",
        "name": "Barbell Bench Press",
        "muscleGroup": "chest",
        "equipment": ["barbell", "bench"],
        "sets": 4,
        "reps": "8-12",
        "restSeconds": 90,
        "notes": "Focus on controlled eccentric phase"
      }
    ]
  }
}
```

---

### Agent 3: Life Sync Agent (Sub-Agent B)

**Framework**: LangGraph SDK (Python)

**System Prompt**:
```
You are a pragmatic logistics and lifestyle coordinator.

Objective: Validate plans against the user's real-world constraints:
time, equipment, and fatigue.

A2A Logic:
- When the Orchestrator sends a proposed plan, check it against the user's schedule
- Explicitly flag conflicts like "user only has a 30-minute gap" or
  "current location has no barbell"
- Provide specific, actionable conflict reports

Tone: Empathetic, realistic, and brief.
```

**Tools**:
- `get_calendar_availability(date: str, duration_minutes: int) -> AvailabilityResult`
- `get_equipment_inventory(location: str) -> EquipmentList`

**Mock Tool Implementations**:

```python
@dataclass
class TimeSlot:
    start: str  # ISO 8601
    end: str
    available: bool
    conflict_reason: str | None

@dataclass
class AvailabilityResult:
    date: str
    slots: list[TimeSlot]
    max_continuous_minutes: int
    recommendation: str

@dataclass
class EquipmentList:
    location: str
    available: list[str]  # ["dumbbells", "pullup_bar", "resistance_bands"]
    missing: list[str]    # ["barbell", "squat_rack"]
```

**Response Format**:
```json
{
  "analysis": {
    "hasConflicts": true,
    "conflicts": [
      {
        "type": "time",
        "severity": "high",
        "message": "User only has a 30-minute gap between 6:00 PM and 6:30 PM",
        "suggestion": "Request a shorter workout (20-30 minutes)"
      },
      {
        "type": "equipment",
        "severity": "medium",
        "message": "Current location (home) has no barbell",
        "suggestion": "Request dumbbell or bodyweight alternatives"
      }
    ],
    "recommendation": "Request a 25-minute dumbbell-only upper body workout"
  }
}
```

---

## Directory Structure

```
a2a-with-agentcore/
├── CLAUDE.md                          # Project steering
├── SPECIFICATION.md                   # This document
├── README.md                          # User documentation
├── makefile                           # Root orchestration
├── etc/
│   └── environment.sh                 # Configuration injection
├── agents/
│   ├── orchestrator/                  # Agent 1: Strands (Python)
│   │   ├── app.py                     # Main application
│   │   ├── a2a/
│   │   │   ├── server.py              # A2A JSON-RPC server
│   │   │   ├── client.py              # A2A HTTP client (single implementation)
│   │   │   └── types.py               # A2A type definitions
│   │   ├── tools/
│   │   │   └── a2a_tools.py           # Strands tools wrapping A2A client
│   │   ├── tests/
│   │   │   └── test_orchestrator.py
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
│   │   │   └── agent.test.ts
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
│       │   └── test_life_sync.py
│       ├── requirements.txt
│       ├── dockerfile
│       └── pyproject.toml
│
├── frontend/
│   ├── app.py                         # Momentum Fitness Streamlit frontend (dark theme)
│   ├── requirements.txt
│   └── .env                           # Frontend configuration
│
├── iac/
│   ├── infrastructure.yaml            # ECR repos, IAM roles, Security Groups
│   ├── cognito.yaml                   # Cognito User Pool (optional, for API GW)
│   ├── apigw.yaml                     # API Gateway (optional A2A passthrough)
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

**Key Implementation Details**:
- Frontend uses `boto3.client("bedrock-agentcore")` to invoke orchestrator (not HTTP/A2A)
- `A2AClient` in orchestrator supports both boto3 (ARNs) and HTTP (URLs) for sub-agent calls
- Agent containers expose standard A2A endpoints (`/`, `/.well-known/agent.json`, `/health`)

---

## Infrastructure

### AgentCore Runtimes

All agents are deployed with `ProtocolConfiguration: A2A`. AgentCore natively routes A2A JSON-RPC requests to the agent containers.

| Agent | Container Port | Protocol | ECR Repository |
|-------|---------------|----------|----------------|
| Orchestrator | 8080 | A2A | a2a-orchestrator |
| Biomechanics Lab | 8080 | A2A | a2a-biomechanics-lab |
| Life Sync | 8080 | A2A | a2a-life-sync |

#### AgentCore CloudFormation (agentcore.yaml)

```yaml
OrchestratorRuntime:
  Type: AWS::BedrockAgentCore::Runtime
  Properties:
    AgentRuntimeName: a2a_orchestrator
    ProtocolConfiguration: A2A
    EnvironmentVariables:
      AWS_REGION: !Ref AWS::Region
      MODEL_ID: us.amazon.nova-lite-v1:0
      # Can use ARNs for boto3 transport:
      BIOMECHANICS_ARN: !GetAtt BiomechanicsLabRuntime.Arn
      LIFESYNC_ARN: !GetAtt LifeSyncRuntime.Arn
      # Or URLs for HTTP transport:
      # BIOMECHANICS_URL: !GetAtt BiomechanicsLabRuntime.AgentRuntimeEndpoint
      # LIFESYNC_URL: !GetAtt LifeSyncRuntime.AgentRuntimeEndpoint
```

The orchestrator's `A2AClient` detects whether to use boto3 (for ARNs) or HTTP (for URLs). Both approaches use the A2A protocol.

### IAM Roles

**AgentCore Execution Role** (shared by all agents):
- ECR: Pull images
- CloudWatch: Logs, Application Signals
- X-Ray: Telemetry
- Bedrock: InvokeModelWithResponseStream
- AgentCore: InvokeAgentRuntime (for inter-agent A2A calls)

### Cognito User Pool (Optional)

Only needed if deploying API Gateway for external access:

- **User Pool**: `a2a-fitness-users`
- **App Client**: `a2a-fitness-client` (with client secret)
- **Resource Server**: `a2a-fitness-api`
  - Scope: `agents/invoke`
- **Token Type**: ID Token for API Gateway authorization

### API Gateway (Optional)

An optional layer for external access with JWT auth. When present, it passes A2A JSON-RPC requests through to AgentCore — no protocol translation.

- **Type**: REST API
- **Authentication**: Cognito JWT Authorizer
- **Behavior**: Transparent A2A passthrough to AgentCore
- **Endpoints**:
  - `POST /` - A2A JSON-RPC (all methods)
  - `GET /.well-known/agent.json` - Agent card (public)

---

## Error Handling

### Retry Strategy

```python
RETRY_CONFIG = {
    "max_attempts": 3,
    "base_delay_seconds": 1,
    "max_delay_seconds": 10,
    "exponential_base": 2,
    "retryable_errors": [
        "ServiceUnavailable",
        "ThrottlingException",
        "Timeout"
    ]
}
```

### Error Response Format

```json
{
  "jsonrpc": "2.0",
  "id": "task-123",
  "error": {
    "code": -32000,
    "message": "Sub-agent unavailable after 3 retries",
    "data": {
      "agent": "biomechanics-lab",
      "lastError": "Connection timeout",
      "retryAttempts": 3
    }
  }
}
```

---

## Testing Strategy

### Unit Tests

Each agent has isolated unit tests in its `tests/` directory:

```bash
# Orchestrator
cd agents/orchestrator && uv run pytest tests/

# Biomechanics Lab
cd agents/biomechanics-lab && npm test

# Life Sync
cd agents/life-sync && uv run pytest tests/
```

### Local Integration Testing

Docker Compose runs all three agents locally with the same code and protocol as deployed:

```bash
make local.compose.up    # Start all agents
make test.integration    # Run integration tests
make local.compose.down  # Stop all agents
```

**docker-compose.yaml** exposes:
- Orchestrator: `http://localhost:8081`
- Biomechanics Lab: `http://localhost:8082`
- Life Sync: `http://localhost:8083`

All integration tests use A2A JSON-RPC requests, validating the exact same protocol path as production.

### Test Scenarios

1. **Happy Path**: User requests hypertrophy workout → Biomechanics Lab returns plan → Life Sync confirms availability → Orchestrator returns plan
2. **Time Conflict**: Life Sync reports 30-minute gap → Orchestrator requests refinement → Biomechanics Lab returns shorter workout
3. **Equipment Conflict**: Life Sync reports no barbell → Orchestrator requests bodyweight alternatives
4. **Sub-Agent Failure**: Biomechanics Lab unavailable → Retry 3x → Return error

---

## Makefile Targets

```makefile
# Infrastructure
make infrastructure          # Deploy ECR, IAM, Security Groups
make cognito                 # Deploy Cognito User Pool (optional)
make apigw                   # Deploy API Gateway (optional)
make agentcore               # Deploy AgentCore runtimes (A2A protocol)

# Build & Deploy Agents
make orchestrator.build      # Build Orchestrator container
make orchestrator.push       # Push to ECR
make biomechanics.build      # Build Biomechanics Lab container
make biomechanics.push       # Push to ECR
make lifesync.build          # Build Life Sync container
make lifesync.push           # Push to ECR
make build.all               # Build all containers
make push.all                # Push all to ECR
make deploy.all              # Deploy all to AgentCore

# Local Development
make local.orchestrator      # Run Orchestrator locally (no container)
make local.biomechanics      # Run Biomechanics Lab locally (no container)
make local.lifesync          # Run Life Sync locally (no container)
make local.compose.up        # Start all via Docker Compose
make local.compose.down      # Stop Docker Compose
make local.compose.logs      # Follow logs

# Testing
make test.unit               # Run all unit tests
make test.integration        # Run integration tests (requires Docker Compose)

# Invocation (A2A JSON-RPC)
make invoke.local            # Send A2A request to local orchestrator
make invoke.deployed         # Send A2A request to deployed orchestrator (SigV4)
make invoke.agentcard        # Fetch orchestrator agent card
```

---

## Sample Interaction

### Local Request

```bash
curl -X POST http://localhost:8081/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "req-001",
    "method": "tasks/send",
    "params": {
      "task": {
        "id": "task-001",
        "message": {
          "role": "user",
          "parts": [
            {
              "type": "text",
              "text": "I want a strength workout for my upper body. I have about an hour and access to a full gym."
            }
          ]
        }
      }
    }
  }'
```

### Deployed Request (SigV4)

```bash
# Using awscurl or equivalent SigV4-signing client
awscurl --service bedrock-agentcore \
  --region us-east-1 \
  -X POST "<agentcore-a2a-endpoint-url>" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "req-001",
    "method": "tasks/send",
    "params": {
      "task": {
        "id": "task-001",
        "message": {
          "role": "user",
          "parts": [
            {
              "type": "text",
              "text": "I want a strength workout for my upper body. I have about an hour and access to a full gym."
            }
          ]
        }
      }
    }
  }'
```

Note: the JSON-RPC payload is **identical**. Only the transport-level auth differs.

### Response

```json
{
  "jsonrpc": "2.0",
  "id": "req-001",
  "result": {
    "taskId": "task-001",
    "status": "completed",
    "result": {
      "message": {
        "role": "assistant",
        "parts": [
          {
            "type": "text",
            "text": "I've created your upper body strength workout. The plan has been validated against your schedule - you have a clear 60-minute window this evening.\n\n**Workout: Upper Body Strength (55 min)**\n\n1. Barbell Bench Press - 4x6 @ RPE 8 (Rest: 3 min)\n2. Weighted Pull-ups - 4x6 (Rest: 3 min)\n3. Overhead Press - 3x8 (Rest: 2 min)\n4. Barbell Rows - 3x8 (Rest: 2 min)\n5. Face Pulls - 3x15 (Rest: 1 min)\n\nAll equipment is available at your gym location. Let me know if you'd like any modifications!"
          },
          {
            "type": "data",
            "data": {
              "workout": {
                "name": "Upper Body Strength",
                "estimatedDuration": 55,
                "exercises": [...]
              },
              "validation": {
                "hasConflicts": false,
                "availableTimeSlot": "18:00-19:00",
                "equipmentVerified": true
              }
            }
          }
        ]
      }
    }
  }
}
```

---

## Dependencies

### Orchestrator (Python)

```
strands-agents>=1.4.0
fastapi>=0.115.0
uvicorn>=0.30.0
httpx>=0.27.0
pydantic>=2.0.0
sse-starlette>=2.0.0
```

Note: No `boto3`, `botocore`, or `bedrock-agentcore` SDK in agent dependencies. The orchestrator calls sub-agents via plain HTTP A2A. AWS SDK dependencies are only needed at the model layer (Strands handles this internally via `BedrockModel`).

### Biomechanics Lab (TypeScript)

```json
{
  "@langchain/langgraph": "^0.2.0",
  "@langchain/aws": "^0.1.0",
  "@langchain/core": "^0.3.0",
  "express": "^4.18.0",
  "zod": "^3.23.0"
}
```

### Life Sync (Python)

```
langgraph>=0.2.0
langchain-aws>=0.2.0
langchain-core>=0.3.0
fastapi>=0.115.0
uvicorn>=0.30.0
pydantic>=2.0.0
sse-starlette>=2.0.0
```

### Frontend (Python)

```
streamlit>=1.30.0
boto3>=1.35.0
python-dotenv>=1.0.0
```

The frontend uses `boto3.client("bedrock-agentcore")` to invoke the orchestrator agent runtime.

---

## Key Architecture Decisions

| Aspect | Implementation | Rationale |
|--------|----------------|-----------|
| Frontend → Orchestrator | `boto3.client("bedrock-agentcore").invoke_agent_runtime()` | Uses AWS SDK with SigV4 auth; AgentCore handles A2A internally |
| Orchestrator → Sub-agents | `A2AClient` with auto-detection (boto3 for ARNs, HTTP for URLs) | Flexible transport while maintaining A2A protocol |
| Agent endpoints | `/` (POST), `/.well-known/agent.json` (GET), `/health` (GET) | Standard A2A protocol compliance |
| Environment variables | `*_ARN` for boto3, `*_URL` for HTTP | Single client implementation with runtime detection |
| Frontend UI | Momentum Fitness (dark theme Streamlit) | Modern, user-friendly workout planning interface |
| Protocol consistency | A2A JSON-RPC format throughout | Inter-agent communication uses standard A2A messages |
| Agent portability | Same container for local and deployed | Environment variables are the only difference |

---

## Request Flow Detail

### Hop 1: Frontend → Orchestrator (AWS SDK)
- **Component**: `frontend/app.py:send_workout_request()`
- **Transport**: AWS SDK (boto3)
- **Service**: `bedrock-agentcore`
- **Method**: `invoke_agent_runtime(agentRuntimeArn=..., payload=...)`
- **Auth**: SigV4 (via AWS profile/credentials)
- **Payload**: A2A JSON-RPC wrapped in AWS API format

### Hop 2: AgentCore → Orchestrator Container (Internal)
- **Component**: AWS AgentCore Runtime
- **Transport**: Internal (AgentCore runtime mechanism)
- **Protocol**: A2A JSON-RPC
- **Auth**: Managed by AgentCore
- **Payload**: Pure A2A JSON-RPC message

### Hop 3: Orchestrator → Sub-agents (A2A with Auto-Detection)
- **Component**: `agents/orchestrator/a2a/client.py:A2AClient`
- **Transport Detection**:
  - If `BIOMECHANICS_ARN` is set → Use `boto3.client("bedrock-agentcore")`
  - If `BIOMECHANICS_URL` is set → Use `httpx` HTTP client
- **Protocol**: A2A JSON-RPC (both transports)
- **Auth**: Execution role (boto3) or none (local HTTP)
- **Payload**: A2A `tasks/send` messages
