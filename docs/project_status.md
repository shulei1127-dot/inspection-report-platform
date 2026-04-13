# Project Status

## Current Phase

Minimal Retention And Batch Cleanup v1 MVP

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
- added issue generation v1 based on parsed service and container states
- implemented minimal explainable rules for failed/inactive services and exited/unhealthy/restarting containers
- updated unified summary generation so `overall_status`, `issue_count`, and `issue_by_severity` now reflect parsed issues
- verified that parsed issues flow through to `report_payload.json` without changing the payload contract
- extended `system_info` parsing to support `ip`, `timezone`, `uptime_seconds`, and `last_boot_at`
- added host issue v1 for missing hostname, kernel version, timezone, and uptime
- verified that host completeness issues are generated through the existing `issues[]` pipeline without changing the contract
- added host issue v2 consistency checks for `uptime_seconds` and `last_boot_at`
- added sanity validation for invalid uptime values including negative, zero, and clearly abnormal values
- added a conservative future-boot check when `last_boot_at` is later than parser generation time
- added `GET /api/tasks/{task_id}` for minimal task-result lookup based on existing task artifacts
- added `GET /api/tasks/{task_id}/report` for DOCX report download by `task_id`
- kept task-result inference file-based without introducing a database
- added `docs/input_bundle_spec_v1.md` to formalize the supported zip input structure, file names, and minimal file formats
- updated parser lookup to prefer the canonical v1 input paths
- aligned fixtures and tests with the input bundle v1 directory layout
- added `GET /api/tasks` for minimal task history visibility without requiring users to remember task IDs manually
- implemented latest-first task ordering based on parsed task timestamp with filesystem fallback
- kept task list generation file-based and aligned its item structure with the existing single-task result format
- added `DELETE /api/tasks/{task_id}` to remove the uploaded archive, workdir, and output directory for a task
- kept cleanup strictly scoped to the exact task-specific paths derived from `task_id`
- added a minimal SQLite-backed `tasks` table for explicit task lifecycle records without introducing a full database stack
- started writing task records at upload creation time and updating them as `unified.json`, `report_payload.json`, and optional `report.docx` artifacts are produced
- updated `GET /api/tasks/{task_id}` and `GET /api/tasks` to prefer database-backed task records while keeping a narrow filesystem fallback for older local artifacts
- updated task deletion so filesystem cleanup also removes the matching database record
- added `POST /api/tasks/cleanup` for manual batch cleanup without introducing a scheduler or background worker
- added minimal retention filters `keep_latest` and `older_than_days`
- kept batch cleanup limited to safe task statuses `rendered`, `completed`, and `failed`, while always skipping `processing`
- kept batch cleanup aligned with exact-path single-task deletion so archive, workdir, outputs, and matching database records are removed together

## Pending

- real log parsing into unified JSON
- richer issue severity and root-cause analysis
- richer host diagnostics beyond information completeness checks
- deeper host time consistency diagnostics beyond basic impossible/future-value checks
- product-line and device-specific multi-template system
- AI analysis workflow
- frontend
- richer persistence layer behavior beyond a single SQLite table

## Notes

- This iteration now includes a minimal SQLite persistence layer but intentionally avoids ORM, migrations, and multi-table design.
- The current upload path synchronously writes parser-generated `unified.json` and `report_payload.json` artifacts.
- The parser is no longer pure stub: `system_info`, `systemctl_status`, and `docker_ps` now produce partial real parsed data, while the rest of the contract still falls back to defaults.
- Issue generation is still rule-based MVP logic and currently only covers a small, explicit status set for services and containers.
- Host issues are currently limited to missing-information checks and do not attempt deeper host diagnosis.
- Host consistency checks now cover a minimal uptime/last-boot relationship, but they still avoid broad clock-skew or NTP judgment.
- `templates/inspection_report.docx` is the current MVP default placeholder template and is intended only to validate the single-template rendering path.
- Report rendering now targets the real Carbone HTTP API, and the adapter shape is aligned with official HTTP API documentation.
- Real local rendering is now verified on this machine with a cached official Carbone image.
- Raw shell-level connectivity to Docker Hub is still inconsistent on this machine, but Docker Desktop proxying is sufficient for image pulls and local Carbone runtime startup.
- Task-result querying and task history now prefer explicit SQLite task records, but summary counts still remain file-derived from `unified.json`.
- Input support is now documented and stabilized for v1, but parser coverage is still intentionally narrow and only covers the currently documented files.
- Task history is now visible through `GET /api/tasks`, but the list is still intentionally minimal and has no pagination, filtering, or search yet.
- Task cleanup now supports manual batch retention filters, but there is still no scheduled cleanup, soft delete, or restore mechanism.
