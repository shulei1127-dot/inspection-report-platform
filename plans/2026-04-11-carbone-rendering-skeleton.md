# 2026-04-11 Carbone Rendering Skeleton

## Goal

Complete the next MVP-sized closed loop for the report rendering layer:
- evaluate whether the current environment can support a real Carbone render
- if not feasible, implement a replaceable rendering adapter layer
- define template conventions, rendering input validation, output path conventions, and non-blocking upload-flow integration

## Environment Assessment

Current local signals:
- `docker` is installed and reachable
- `node` and `npm` are installed
- no `carbone` executable is currently available in `PATH`
- no Carbone-specific environment variables are currently configured
- no real DOCX template currently exists in the repository

Conclusion for this iteration:
- a trustworthy "real render success" loop is not currently feasible without additional external provisioning
- this iteration should implement a rendering service skeleton with:
  - template path convention
  - payload validation
  - output path convention
  - structured rendering errors
  - a replaceable adapter boundary
- do not fake a successful DOCX render

## Scope

In scope:
- add report rendering service in `app/services/`
- define `templates/inspection_report.docx` as the default template path convention
- read rendering input from `report_payload.json`
- validate the payload against the report payload schema before rendering
- define output path as `outputs/{task_id}/report.docx`
- add optional, non-blocking integration from the upload flow
- return `report_file_path` when a report is actually generated
- add tests for validation and missing-template behavior
- update project status docs

Out of scope:
- real log parsing
- modifying unified JSON contract for rendering convenience
- database integration
- guaranteed real Carbone execution in this environment

## Planned Behavior

1. By default, report rendering is disabled in the upload flow.
2. When rendering is disabled:
   - upload flow still succeeds
   - `report_payload.json` still persists
   - `report_file_path` remains `null`
3. When rendering is enabled:
   - service validates `report_payload.json`
   - service validates template existence
   - service calls a rendering adapter
4. In the current environment, the default adapter reports Carbone as unavailable instead of pretending success.
5. Later, only the adapter implementation should need replacement to support real Carbone.

## Template And Output Conventions

- template directory: `templates/`
- default template path: `templates/inspection_report.docx`
- rendered output path: `outputs/{task_id}/report.docx`

## Error Structure

Use structured rendering errors with stable codes, for example:
- `report_payload_missing`
- `invalid_report_payload`
- `template_missing`
- `carbone_unavailable`
- `render_failed`

These errors should exist in the rendering service even if they are not all surfaced directly in the upload API response yet.

## Validation Plan

1. Run `pytest`
2. Start FastAPI with `uvicorn`
3. Verify `GET /health`
4. Verify upload flow still works when rendering is disabled
5. Verify rendering service rejects missing payload input
6. Verify rendering service rejects missing template input
7. Verify `report_file_path` remains empty unless a real render succeeds

## Risks

- accidental fake-success behavior must be avoided
- rendering concerns must stay separate from unified JSON concerns
- upload flow must remain stable even when rendering is unavailable
