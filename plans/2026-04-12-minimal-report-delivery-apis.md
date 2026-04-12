# 2026-04-12 Minimal Report Delivery APIs

## Goal

Add the smallest API delivery layer on top of the current file-based workflow so
users can:

1. query task results by `task_id`
2. download `report.docx` by `task_id`

## Scope

In scope:
- `GET /api/tasks/{task_id}`
- `GET /api/tasks/{task_id}/report`
- file-based task status inference
- tests for query and download behavior

Out of scope:
- database-backed task persistence
- frontend work
- parser changes
- workflow refactor

## Minimal Status Inference Rules

Because the project still has no database, task status is inferred from files:

- `rendered`:
  - `outputs/{task_id}/report.docx` exists
- `completed`:
  - `workdir/{task_id}/unified.json` exists
  - `workdir/{task_id}/report_payload.json` exists
  - rendered report does not exist
- `processing`:
  - task paths exist but final artifacts are incomplete

If no task evidence exists at all, return a structured `404`.

## Response Shape

Keep the response style aligned with the current task contracts:

- top-level `success`
- top-level `data`
- structured `error` for failures

`GET /api/tasks/{task_id}` should return at least:

- `task_id`
- `status`
- `unified_json_path`
- `report_payload_path`
- `report_file_path`

## Download Behavior

`GET /api/tasks/{task_id}/report`:

- return a file download when `report.docx` exists
- return structured `404` when report is missing
- do not trigger rendering implicitly in this loop

## Validation Plan

1. query an existing task result
2. download an existing report file
3. verify clear `404` when report is missing
4. run full test suite
