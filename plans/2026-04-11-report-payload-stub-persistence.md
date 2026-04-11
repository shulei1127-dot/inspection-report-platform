# 2026-04-11 Report Payload Stub Persistence

## Goal

Complete the next MVP-sized closed loop:
- after `unified.json` is written, generate a minimal valid `report_payload.json`
- persist it to `workdir/{task_id}/report_payload.json`
- return `report_payload_path` in the task creation response

This iteration does not integrate Carbone.

## Scope

In scope:
- use the existing report payload schema and mapper as the base
- refine the mapper into a clearly documented stub-compatible implementation
- generate `report_payload.json` from `UnifiedJsonV1`
- persist `report_payload.json` after `unified.json` is written
- update task success response to include `report_payload_path`
- update tests and docs

Out of scope:
- Carbone rendering
- real log parsing
- changing the unified JSON contract to suit templates
- adding document templates

## Contract Alignment

Implementation follows `~/.codex/skills/inspection-report-platform/references/contracts.md`.

The generated report payload must:
- remain separate from unified JSON
- use its own schema/model
- use `payload_version: "report-payload/v1"`
- stay template-friendly and ready for later DOCX consumption

## Planned Stub Defaults

Because the current parser is still a stub, the mapper will use honest placeholder values where needed:

1. `report.title`
   - default to `"Inspection Report"`
2. `summary.overall_status_label`
   - map from unified JSON status using fixed labels
3. `service_rows`
   - empty list when unified JSON has no services
4. `container_rows`
   - empty list when unified JSON has no containers
5. `issue_rows`
   - empty list when unified JSON has no issues
6. `highlights`
   - add one simple stub-friendly highlight such as upload/extraction success
7. `recommendations`
   - add one simple recommendation that real parsing should be enabled later
8. `appendix`
   - include only lightweight metadata that may help templates or debugging, such as parser name

These defaults keep the payload valid and useful for template work without pretending to contain real inspection conclusions.

## Design Decisions

1. Keep the mapper logic in `app/services/report_payload_mapper.py`.
2. Add a persistence helper near the mapper so the task service stays orchestration-focused.
3. Read `UnifiedJsonV1` from the in-memory model already produced in the upload flow rather than re-reading `unified.json` from disk inside the same request.
4. Persist `report_payload.json` with UTF-8 and pretty formatting.
5. Keep Carbone completely out of the current flow.

## Validation Plan

1. Run `pytest`
2. Start FastAPI with `uvicorn`
3. Verify `GET /health`
4. Verify `POST /api/tasks` writes `report_payload.json`
5. Validate the persisted payload with the report payload schema

## Risks

- placeholder strings must stay clearly generic and not imply real system findings
- mapper changes must not back-drive changes into the unified JSON contract
