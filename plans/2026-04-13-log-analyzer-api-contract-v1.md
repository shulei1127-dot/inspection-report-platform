## Goal

Add a formal `docs/log_analyzer_api_v1.md` document that defines the first stable API boundary for a future standalone log-analyzer-service.

## Scope

- add `docs/log_analyzer_api_v1.md`
- align the document with the current platform-side analyzer request/response models
- document service goal, scope boundary, request envelope, response envelope, errors, timeout expectations, and non-goals
- update `README.md` and `docs/project_status.md` only if minimal synchronization is needed

## Out Of Scope

- implementing the standalone analyzer service
- changing parser logic
- changing task orchestration flow
- adding new analyzer request modes beyond documented placeholders

## Key Decisions

- v1 keeps `source` as an extensible object and only supports `source.type = "directory"`
- v1 explicitly does not support archive upload to the analyzer service
- analyzer responses are wrapped in `analyze-response/v1`; the service must not return a bare `UnifiedJsonV1`
- document service-side error shapes even though the current platform remote adapter only strictly validates successful `200` responses
- keep the document aligned with current `AnalyzeRequestV1`, `AnalyzeResponseV1`, and `RemoteLogAnalyzer`

## Verification Plan

- read current analyzer schema and adapter code before writing the document
- review the final document against:
  - `app/schemas/log_analyzer.py`
  - `app/services/log_analyzer.py`
  - `tests/test_log_analyzer.py`
  - `references/contracts.md`
- run a lightweight local consistency check after edits
