## Goal

Implement the first runnable version of `log-analyzer-service` with:

- real `GET /health`
- real `POST /analyze` happy path
- directory-source validation
- structured analyzer errors
- migrated parser support for `system_info`, `systemctl_status`, and `docker_ps`

## Scope

- implement analyzer-local request/response and unified JSON schemas
- implement analyzer service orchestration
- implement analyzer parser migration for current supported files
- add minimal API tests under `log-analyzer-service/tests/`
- update analyzer README and root project status

## Out Of Scope

- archive upload support
- shared contracts package
- database or persistence
- async jobs
- platform main-flow refactor

## Key Decisions

- analyzer keeps its own schema files and does not import platform internals
- v1 only supports `source.type = "directory"`
- invalid `source.type` and missing directories return structured JSON errors
- request version stays constrained to `analyze-request/v1`
- parser logic is copied from the current platform parser into the analyzer subtree and adjusted locally

## Verification Plan

- `python3 -m compileall log-analyzer-service/app`
- `cd log-analyzer-service && ../.venv/bin/pytest`
- optional import check for `app.main`
