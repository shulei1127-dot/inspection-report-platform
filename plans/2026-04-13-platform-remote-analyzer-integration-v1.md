## Goal

Validate and harden the platform's remote analyzer mode against the real `log-analyzer-service` implementation without refactoring the main workflow.

## Scope

- add platform-side tests for remote analyzer happy path
- add platform-side tests for analyzer unreachable and invalid-response failure modes
- verify real local integration with:
  - `log-analyzer-service`
  - platform in `ANALYZER_MODE=remote`
- update documentation with minimal startup and validation guidance

## Out Of Scope

- parser refactor
- archive upload mode for analyzer service
- shared contracts package
- report pipeline redesign
- async task execution

## Key Decisions

- keep platform workflow unchanged; only exercise the existing analyzer seam
- use `RemoteLogAnalyzer` in tests with `httpx.MockTransport`
- perform real manual verification by running analyzer and platform on separate local ports
- keep status expectations explicit:
  - `analyzing`
  - `completed`
  - `rendered`
  - `analyze_failed`

## Verification Plan

- `python3 -m compileall app tests`
- `.venv/bin/pytest tests/test_tasks.py tests/test_log_analyzer.py`
- optional full `.venv/bin/pytest`
- real local integration:
  - start `log-analyzer-service` on `127.0.0.1:8090`
  - start platform with `ANALYZER_MODE=remote` on `127.0.0.1:8013`
  - verify `/health`
  - upload a spec-v1 archive through `POST /api/tasks`
  - inspect `unified.json`, `report_payload.json`, and task status
