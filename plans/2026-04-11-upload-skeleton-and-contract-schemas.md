# 2026-04-11 Upload Skeleton And Contract Schemas

## Goal

Complete one MVP-sized closed loop for `inspection-report-platform`:
- land unified JSON v1 schemas
- land `POST /api/tasks` request/response contracts
- implement the upload and unzip skeleton
- add a report-payload mapper skeleton without wiring it into the main flow

This iteration does not include a real parser, database, or Carbone integration.

## Scope

In scope:
- Pydantic models under `app/schemas/` for unified JSON v1
- Pydantic models for task responses and report payload contract
- `POST /api/tasks` route
- upload validation for zip only
- `task_id` generation
- save raw archive to `uploads/`
- extract archive to `workdir/{task_id}/`
- skeleton response with task metadata only
- tests for upload success and non-zip failure
- update `docs/project_status.md`

Out of scope:
- real log parsing
- unified JSON file generation in the main flow
- report rendering
- background jobs
- database persistence

## Contract Alignment

Implementation follows `~/.codex/skills/inspection-report-platform/references/contracts.md` first.

Small implementation note:
- `POST /api/tasks` uses `multipart/form-data`, so the request contract will be represented in code as `UploadFile` plus `Form(...)` fields for `parser_profile` and `report_lang`
- a small Pydantic request model may still exist for business-level validation/defaults, but FastAPI cannot accept the upload file as a plain JSON body model

## Design Decisions

1. Keep upload flow synchronous for MVP.
2. Return contract-shaped task metadata even though parsing is not wired yet.
3. Keep parsing placeholders explicit by returning:
   - `status: "completed"` when upload and extraction succeed
   - `unified_json_path: null`
   - `report_payload_path: null`
   - zero-count summary
4. Place filesystem and task-id logic in `app/services/`.
5. Keep the route thin and let services own archive handling.
6. Create a separate mapper skeleton for `unified JSON -> report payload` but do not call it from `POST /api/tasks`.

## Planned File Changes

- `app/schemas/`
  - add unified JSON v1 models
  - add task request/response models
  - add report payload models
- `app/services/`
  - add upload task service
  - add report payload mapper skeleton
- `app/api/`
  - add task endpoint
  - register route
- `tests/`
  - add upload endpoint tests
- `docs/project_status.md`
  - mark the upload skeleton loop complete

## Validation Plan

1. Run `pytest`
2. Start FastAPI locally with `uvicorn`
3. Verify `GET /health`
4. Verify `POST /api/tasks` with a real zip upload
5. Verify non-zip upload returns a contract-shaped error response

## Risks

- multipart request handling can become awkward if over-modeled, so keep the endpoint contract simple
- zip validation must check both filename suffix and archive validity
- extracted test artifacts must stay scoped to temporary test directories where possible
