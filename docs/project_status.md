# Project Status

## Current Phase

Real Parser V1 MVP

## Completed In This Iteration

- initialized repository structure
- established plan-first development rule via `plans/`
- added FastAPI minimum runnable skeleton
- implemented `GET /health`
- added baseline docs and environment template
- added a basic health endpoint test
- added unified JSON v1 schema models
- added task and report payload schema models
- implemented `POST /api/tasks` upload skeleton
- added zip-only validation, task id generation, upload persistence, and extraction to `workdir/{task_id}/`
- added a parser stub that generates a minimal valid `unified.json` after extraction
- added `unified.json` persistence to `workdir/{task_id}/unified.json`
- updated the task response to return `unified_json_path`
- wired unified JSON to report payload mapping into the upload flow
- added `report_payload.json` persistence to `workdir/{task_id}/report_payload.json`
- updated the task response to return `report_payload_path`
- added a replaceable report rendering service layer for future Carbone integration
- defined default template convention at `templates/inspection_report.docx`
- defined rendered output convention at `outputs/{task_id}/report.docx`
- added non-blocking upload-flow integration for optional report rendering
- updated the task response to support `report_file_path`
- added a real default DOCX template asset at `templates/inspection_report.docx`
- aligned the default template placeholders with the current report payload contract
- added upload endpoint tests for success, non-zip failure, missing file, unified JSON generation, and report payload generation
- added a real HTTP-based Carbone adapter implementation for future on-premise runtime integration
- added a dedicated `POST /api/tasks/{task_id}/render-report` validation entrypoint
- added structured Carbone runtime error branches for unreachable runtime, failed status checks, and failed render requests
- added rendering service tests for payload validation, template existence, missing-template handling, disabled-render compatibility, and Carbone-unreachable behavior
- aligned the Docker startup guidance with Carbone's official Docker repository guidance
- documented that DOCX-to-DOCX generation does not require LibreOffice, while conversions such as PDF do
- verified the current template marker style and loop helper markers against official Carbone repetition syntax
- verified that the local Docker daemon is healthy and that a cached official `carbone/carbone-ee:latest` image is available on this machine
- confirmed the current shell still cannot directly open TCP 443 to Docker Hub endpoints, but Docker Desktop proxying allows `docker pull carbone/carbone-ee:latest` to succeed
- successfully started a real local Carbone container and confirmed `GET /status` returns `200`
- successfully completed one real end-to-end render from `report_payload.json` to `outputs/{task_id}/report.docx`
- added a minimal `scripts/verify_carbone_render.sh` acceptance script for repeatable local render validation
- replaced part of the parser stub behavior with real parser v1 support for `system_info`, `systemctl_status`, and `docker_ps`
- added fixture inputs for parser v1 coverage under `tests/fixtures/real_parser_v1`
- verified that parsed `host_info`, `services`, and `containers` now flow into `unified.json`
- updated task creation to return summary counts derived from the generated `unified.json`
- kept missing parser inputs on safe fallback behavior so `unified-json/v1` stays valid even when known files are absent

## Pending

- real log parsing into unified JSON
- product-line and device-specific multi-template system
- AI analysis workflow
- frontend
- persistence layer

## Notes

- This iteration intentionally avoids database and real parser integration.
- The current upload path synchronously writes parser-generated `unified.json` and `report_payload.json` artifacts.
- The parser is no longer pure stub: `system_info`, `systemctl_status`, and `docker_ps` now produce partial real parsed data, while the rest of the contract still falls back to defaults.
- `templates/inspection_report.docx` is the current MVP default placeholder template and is intended only to validate the single-template rendering path.
- Report rendering now targets the real Carbone HTTP API, and the adapter shape is aligned with official HTTP API documentation.
- Real local rendering is now verified on this machine with a cached official Carbone image.
- Raw shell-level connectivity to Docker Hub is still inconsistent on this machine, but Docker Desktop proxying is sufficient for image pulls and local Carbone runtime startup.
