# CI Smoke Lane

## Goal

为 remote analyzer 提供一条最小、稳定的自动回归入口，覆盖：

- root platform tests
- `log-analyzer-service` tests
- remote analyzer success smoke
- remote analyzer failure smoke

## Workflow

Current workflow file:

- `.github/workflows/remote-analyzer-smoke.yml`

## Required Jobs

### `unit-tests`

Runs:

- `.venv/bin/pytest`
- `cd log-analyzer-service && ../.venv/bin/pytest`

### `remote-analyzer-smoke-success`

Runs:

- `./scripts/verify_remote_analyzer_integration.sh`

Default CI setting:

- `VERIFY_RENDER=false`

This keeps Carbone out of the required CI path.

### `remote-analyzer-smoke-failure`

Runs:

- `./scripts/verify_remote_analyzer_failure_modes.sh`

## Environment Assumptions

- GitHub Actions `ubuntu-latest`
- Python `3.12`
- repository-local `.venv`
- root dependencies from `requirements.txt`
- analyzer subtree dependencies from `log-analyzer-service/requirements.txt`

## Startup Order For Success Smoke

1. create sample input bundle
2. start `log-analyzer-service`
3. start platform with `ANALYZER_MODE=remote`
4. upload the sample bundle
5. validate `unified.json` and `report_payload.json`

## Startup Order For Failure Smoke

1. create sample input bundle
2. start platform in remote mode
3. point platform to:
   - an unreachable analyzer port, or
   - a temporary mock analyzer process
4. upload the sample bundle
5. validate failure response and task detail error fields

## Optional Checks

Kept out of the required workflow:

- Carbone render verification

Reason:

- it depends on Docker image/runtime availability
- it is better suited to an optional smoke job or manual verification lane
