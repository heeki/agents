# Strands Agent on ECS Fargate

This repository contains a simple Strands FastAPI service and deploys it to ECS Fargate behind an HTTPS Application Load Balancer (ALB).

## Project Structure

```
agents/
└── strands-on-fargate/
    ├── agent/
    │   ├── app.py                    # FastAPI app exposing /ping and /invocations
    │   └── lib/encoders.py           # Encoders
    ├── etc/
    │   ├── environment.template      # Configuration file template
    │   └── environment.sh            # Active configuration file, sourced by makefile
    ├── iac/
    │   ├── infrastructure.yaml       # VPC-facing bits: ALB, Target Group, SGs, ECR
    │   └── ecs.yaml                  # ECS Cluster, TaskDefinition, Service
    ├── dockerfile                    # Container image for the app
    ├── makefile                      # Build, publish, deploy, and test targets
    ├── requirements.txt              # Python dependencies
    └── README.md
```

## Prerequisites

- Python 3.12+
- Docker or Podman (targets use Podman by default)
- AWS CLI configured with a profile able to create CloudFormation, ECR, ELBv2, ECS resources

## Quick Start

1) Initialize environment

```bash
cd strands-on-fargate
uv pip install -r requirements.txt
cp etc/environment.template etc/environment.sh
# edit etc/environment.sh with your values
```

2) Deploy shared infrastructure (ALB, Target Group, SGs, ECR)

```bash
make infrastructure
# capture outputs and update environment variables if your workflow requires them
```

3) Build and publish the container image

```bash
make podman        # build, login, tag, push to ECR
```

4) Create or update the ECS Cluster and Service

```bash
make ecs           # package + deploy the ECS stack
```

5) Test

```bash
# Local service (direct)
make local.agent
make local.test

# Through ALB (deployed)
make ecs.test
```

## Application Endpoints

- GET `/ping` → `{ "message": "pong" }` (health)
- POST `/invocations` with body `{ "prompt": "..." }` → streams plain text tokens (text/plain)

The app binds to `0.0.0.0:8080` by default. The ECS task definition maps container port `8080`, and the target group listens and health checks on port `8080` with path `/ping`.

## Environment Variables

Edit `etc/environment.sh` (copied from the template). Key values used by the Makefile include:

- **AWS CLI**: `PROFILE`, `REGION`, `BUCKET`
- **ECR**: `C_REPO_BASE`, `C_REPO_IMAGE`, `C_VERSION`, `C_REPO_URI`, `C_TAG`
- **Build/Run**: `PLATFORM_DEPLOY` (e.g., `linux/arm64`), `HOST_PORT`, `CONTAINER_PORT`
- **ECS/SAM**: `INFRASTRUCTURE_TEMPLATE`, `INFRASTRUCTURE_STACK`, `INFRASTRUCTURE_PARAMS`, `ECS_TEMPLATE`, `ECS_STACK`, `ECS_PARAMS`
- **Domain**: `P_DOMAINNAME` (for `make ecs.test`)
- **Invocation**: `P_PROMPT`

Increment `C_VERSION` before pushing new images to ensure services pull the latest tag.

## Local Development

Run directly:

```bash
make local.agent
make local.test
```

Run in container with your AWS credentials:

```bash
make podman.run
# or equivalent docker run, ensuring ~/.aws is mounted for credentials and AWS_PROFILE/REGION are set
```

## Deployment Notes

- Architecture: The Dockerfile currently targets ARM64. The ECS task definition sets `RuntimePlatform` to ARM64. If you change one, change the other, or publish a multi-arch image.
- Ports: Ensure the task security group allows inbound from the ALB security group on port `8080` (not `8000`).
- Health checks: The target group is configured with `HealthCheckPath: /ping` and `HealthCheckPort: 8080`.
- If you change container ports, architecture, or health check path, update both the Dockerfile/app and the CloudFormation templates in `iac/` accordingly.


## Troubleshooting

- ALB shows targets unhealthy / Request timed out
  - Confirm the task security group allows ingress from the ALB SG on port `8080`.
  - Verify the app is listening on `0.0.0.0:8080` and `/ping` responds quickly.

- Exec format error (`exec /usr/local/bin/uv: exec format error`)
  - Architecture mismatch. Ensure the image architecture matches the ECS TaskDefinition `RuntimePlatform` (e.g., `ARM64`). Or publish a multi-arch image.

- Container build fails compiling dependencies (e.g., `psutil` on Alpine)
  - Install build prerequisites during image build (e.g., `apk add --no-cache --virtual .build-deps build-base python3-dev linux-headers`) or switch to a Debian/Ubuntu base that has prebuilt wheels available.

- Credentials errors (`botocore.exceptions.NoCredentialsError`)
  - For local runs, pass env vars or mount `~/.aws` into the container and set `AWS_PROFILE`/`AWS_REGION`.

## Make Targets

Common targets (respect values from `etc/environment.sh`):

- `make infrastructure` — package and deploy ALB/SGs/TargetGroup/ECR
- `make podman` — build, login, tag, and push the app image to ECR
- `make podman.run` — run the built image locally with AWS creds mounted
- `make local.agent` — run the app locally with `uv`
- `make local.test` — curl the local `/invocations` endpoint
- `make ecs` — package and deploy the ECS cluster, task, and service
- `make ecs.test` — invoke `/invocations` via the ALB domain


