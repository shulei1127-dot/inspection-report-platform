# 2026-04-11 Unified JSON Stub Persistence

## Goal

Complete the next MVP-sized closed loop:
- after zip upload and extraction, generate a minimal valid unified JSON v1 object
- persist it to `workdir/{task_id}/unified.json`
- return `unified_json_path` in the task creation response

This iteration does not implement real log parsing.

## Scope

In scope:
- add a parser stub service in `app/services/`
- scan the extracted directory structure
- generate a minimal legal `UnifiedJsonV1` object
- write `unified.json` into the task workdir
- update the task success response to include `unified_json_path`
- add or update tests
- update `docs/project_status.md`

Out of scope:
- real log content parsing
- service detection from log content
- container detection from log content
- issue detection from log content
- report payload generation in the main flow
- Carbone integration

## Contract Alignment

Implementation follows `~/.codex/skills/inspection-report-platform/references/contracts.md`.

The generated JSON must explicitly include:
- `schema_version: "unified-json/v1"`
- all required top-level fields from the v1 contract

## Planned Simplifications

Because this is a parser stub, some fields will intentionally use placeholders or derived defaults:

1. `host_info.hostname`
   - derive from the first archive stem when practical
   - otherwise fall back to `"unknown-host"`
2. `summary`
   - all counts default to `0`
   - `overall_status` defaults to `"unknown"` because no real inspection logic exists yet
3. `services`
   - empty list
4. `containers`
   - empty list
5. `issues`
   - empty list
6. `parser`
   - include a lightweight stub identity such as `upload-parser-stub`
7. `metadata`
   - only include simple scan metadata values that fit the current schema, such as extracted file count

These simplifications keep the output legal and honest without pretending to parse real system state.

## Design Decisions

1. Keep the parser stub in `app/services/` because it belongs to business workflow, not API.
2. Return a Pydantic `UnifiedJsonV1` model from the stub service.
3. Persist JSON with UTF-8 and pretty formatting for debugging.
4. Keep the upload route thin and let the task service orchestrate extraction plus stub generation.
5. Avoid wiring the report payload mapper into the upload flow in this iteration.

## Validation Plan

1. Run `pytest`
2. Start FastAPI with `uvicorn`
3. Verify `GET /health`
4. Verify `POST /api/tasks` writes `workdir/{task_id}/unified.json`
5. Verify the persisted JSON can be validated by the `UnifiedJsonV1` schema

## Risks

- placeholder values must stay clearly marked as stub-derived defaults
- schema drift is possible if `contracts.md` changes later, so tests should validate the persisted JSON through the model
