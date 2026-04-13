## Goal

Introduce an internal `LogAnalyzer` abstraction so the platform no longer calls the parser implementation directly, refine task lifecycle statuses around analyze/render boundaries, and add the first batch of analyzer contract tests.

## Scope

- add analyzer request/response contract models for platform-internal use
- add `LogAnalyzer`, `LocalLogAnalyzer`, and `RemoteLogAnalyzer`
- add analyzer-related settings:
  - `ANALYZER_MODE`
  - `ANALYZER_BASE_URL`
  - `ANALYZER_TIMEOUT_SECONDS`
  - `ANALYZER_RETRY_COUNT`
- switch `task_service` from direct parser calls to the analyzer abstraction
- refine task statuses to:
  - `analyzing`
  - `analyze_failed`
  - `completed`
  - `render_failed`
  - `rendered`
- add first-batch contract tests for analyzer request/response validation and platform integration

## Out Of Scope

- standalone analyzer service repository
- `docs/log_analyzer_api_v1.md`
- analyzer-side archive upload mode
- retry backoff beyond a bounded simple loop

## Key Decisions

### Shared boundary

The platform and future analyzer service share protocol contracts, not internal import paths. In this phase, contract models live in the platform only to support the adapter refactor and tests, but the service boundary is modeled as versioned request/response contracts.

### Request shape

The analyzer request keeps a `source` object from day one. v1 only implements directory mode:

```json
{
  "request_version": "analyze-request/v1",
  "task_id": "tsk_xxx",
  "source": {
    "type": "directory",
    "path": "/abs/path/to/workdir/tsk_xxx"
  }
}
```

This preserves room for future modes without breaking the endpoint shape.

### Status mapping

This phase removes coarse platform success/failure reporting for analysis/render flow. The minimum task statuses become:

- `analyzing`
- `analyze_failed`
- `completed`
- `render_failed`
- `rendered`

For now, pre-render upload and extraction failures are also normalized to `analyze_failed` once a task record has been created. This keeps the lifecycle simple in v1 without introducing additional states such as `uploaded` or `extract_failed`.

### Contract testing

Contract tests ship in the same phase as the abstraction. Minimum coverage:

- local analyzer response validates against `analyze-response/v1`
- remote analyzer validates and parses a versioned analyzer response
- platform upload flow can run through the analyzer abstraction
- analyzer failure transitions task status to `analyze_failed`

## Verification Plan

- `python3 -m compileall app tests`
- `pytest tests/test_log_analyzer.py tests/test_tasks.py`
- optional full `pytest`
