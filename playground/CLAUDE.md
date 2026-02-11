# Project Steering

## Directory Structure
- `agents/`: Individual agent logic directories.
  - `agent_name/`: Logic, tests, and local dependencies.
- `backend/`: Backend business logic exposed via API.
- `etc/`: Configuration management.
  - `environment.sh`: Source of truth for all injectable parameters.
- `frontend/`: Frontend used for interacting with the backend.
- `iac/`: Infrastructure as Code (AWS CloudFormation and AWS SAM).
- `makefile`: Root orchestration for builds, deployments, and local runs.

## Build & Command Tooling
- Primary Interface: Always check the `makefile` for available commands before suggesting custom scripts.
- Config Injection: Commands must source `etc/environment.sh`.
- Dependency Management (Python): Use `uv`. 
  - Commands: `uv pip install`, `uv venv`. 
  - Each agent in `agents/` should have its own `.venv` managed via `uv`.
- Dependency Management (TypeScript): Use `npm`.
  - Ensure `node_modules` stay within the relevant directory. 

## Coding Standards
### Python
- Use Type Hints for all function signatures.
- Prefer `unittest` for testing within agent subdirectories.
- Follow PEP 8 style guidelines.

### TypeScript
- Use ESM (ECMAScript Modules).
- Strict typing required (no `any` unless absolutely necessary).

### AWS / IaC
- Follow the principle of least privilege in IAM templates within `iac/`.
- Use environment-based naming conventions (e.g., `resource-name-${STAGE}`).
- Deployments use the SAM CLI.

### Backends
- Use Python and FastAPI for backend APIs.
- Build unit tests for ensuring that responses match expected outcomes.

### Frontends
- Use Typescript and React/Vite for frontend user experience.

## Deployment Workflow
1. Update parameters in `etc/environment.sh`.
2. Execute via `make <target>`.
