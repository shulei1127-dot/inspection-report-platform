# Architecture

## Positioning

This project is the backend platform for:
- receiving log packages
- parsing uploaded artifacts
- generating inspection report inputs
- integrating with future document-generation capabilities such as Carbone

The current implementation is intentionally limited to the bootstrap MVP.

## Current Layering

### `app/main.py`
- FastAPI application entrypoint
- application bootstrap and router registration

### `app/api/`
- HTTP route definitions
- request and response exposure boundary

### `app/schemas/`
- shared request and response schemas
- foundation for future unified JSON outputs

### `app/services/`
- business logic layer
- reserved for upload orchestration, parsing flows, and report preparation

### `app/core/`
- configuration and core application wiring

### `app/utils/`
- reusable helper functions

## Planned Near-Term Flow

1. Client uploads a zip log package to `POST /api/tasks`
2. Platform stores the package in `uploads/`
3. Platform extracts the package to `workdir/{task_id}/`
4. Platform returns task metadata
5. Later stages parse logs into a unified JSON contract
6. Report generation integrates with Carbone in a later phase

## Storage Strategy

- `uploads/`: raw uploaded zip files
- `workdir/`: extracted and task-scoped working directories
- `outputs/`: generated artifacts and future report outputs

## Non-Goals In Current Scope

- database integration
- frontend application
- AI analysis
- report generation
- task persistence beyond in-memory/bootstrap stage
