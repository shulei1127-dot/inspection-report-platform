# Inspection Report Platform

`inspection-report-platform` is a FastAPI-based backend for log package ingestion, parsing, and inspection report generation.

This repository currently contains the MVP bootstrap:
- FastAPI backend skeleton
- `GET /health` health check
- Project conventions and baseline documentation

The upload task flow (`POST /api/tasks`) now accepts supported log archives and drives the current MVP pipeline.

## Project Structure

```text
app/
  api/
  core/
  schemas/
  services/
  utils/
docs/
examples/
outputs/
plans/
tests/
uploads/
workdir/
```

## Quick Start

1. Create a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Start the server:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

4. Verify the health endpoint:

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok","service":"inspection-report-platform"}
```

The running service also exposes a minimal homepage:

```bash
http://127.0.0.1:8000/
```

Minimal local persistence now uses SQLite through Python's standard library:

```bash
TASKS_DB_PATH=tasks.sqlite3
```

If unset, task records are stored in `./tasks.sqlite3`.

The upload flow now resolves log parsing through an internal analyzer abstraction:

```bash
ANALYZER_MODE=local
ANALYZER_BASE_URL=http://127.0.0.1:8090
ANALYZER_TIMEOUT_SECONDS=30
ANALYZER_RETRY_COUNT=0
```

Current modes:

- `local`: use the in-process analyzer implementation that wraps the existing parser
- `remote`: call a future external analyzer service over HTTP

Supported upload archive formats:

- `.zip`
- `.tar.gz`
- `.tgz`

## Carbone Runtime

The repository now includes a real HTTP-based Carbone adapter and a dedicated render endpoint:

- `GET /api/tasks`
- `GET /api/tasks/{task_id}`
- `DELETE /api/tasks/{task_id}`
- `POST /api/tasks/cleanup`
- `POST /api/tasks/{task_id}/render-report`
- `GET /api/tasks/{task_id}/report`

The current MVP keeps one fixed template:

- `templates/inspection_report.docx`

The preferred local reproduction path is Docker-based Carbone On-Premise:

```bash
docker run -t -i --rm --platform linux/amd64 -p 4000:4000 carbone/carbone-ee
```

On this repository's current macOS Apple Silicon environment, a cached `linux/arm64`
`carbone/carbone-ee:latest` image also runs successfully with:

```bash
docker run -d --rm --name inspection-carbone -p 4000:4000 carbone/carbone-ee:latest
curl http://127.0.0.1:4000/status
```

Recommended environment variables:

```bash
CARBONE_BASE_URL=http://127.0.0.1:4000
CARBONE_API_TOKEN=
CARBONE_API_TIMEOUT_SECONDS=30
CARBONE_VERSION=5
REPORT_RENDERING_ENABLED=false
```

Notes:

- The backend only renders from `report_payload.json`; it does not render directly from unified JSON.
- Task detail and task list now prefer SQLite-backed task records, with a narrow filesystem fallback for older local artifacts created before the database layer existed.
- Manual batch cleanup is now available through `POST /api/tasks/cleanup` with the minimal retention filters `keep_latest` and `older_than_days`.
- For Carbone On-Premise, authentication is disabled by default unless you explicitly enable it.
- Carbone supports direct DOCX-to-DOCX generation without LibreOffice. LibreOffice is required when you need format conversion such as DOCX-to-PDF.
- Official Docker variants include `slim` for minimal runtime and `latest/full` for LibreOffice-enabled runtime.
- The current shell still cannot directly open raw TCP 443 connections to `registry-1.docker.io`, but Docker Desktop is configured with its own proxy path and `docker pull carbone/carbone-ee:latest` succeeds on this machine.
- If the Carbone image cannot be pulled or the runtime cannot be reached, the backend returns structured render errors and does not fake `report.docx` generation.

## Real Render Verification

The repository now includes a minimal verification script for the real render path:

```bash
./scripts/verify_carbone_render.sh
```

The script:

- starts a local Carbone container from the cached official image
- waits for `GET /status`
- starts the FastAPI app on a temporary port
- uploads a small archive through `POST /api/tasks`
- calls `POST /api/tasks/{task_id}/render-report`
- verifies that `outputs/{task_id}/report.docx` exists and is a valid DOCX

If you prefer to verify manually:

```bash
docker run -d --rm --name inspection-carbone -p 4000:4000 carbone/carbone-ee:latest
curl http://127.0.0.1:4000/status

APP_HOST=127.0.0.1 APP_PORT=8012 CARBONE_BASE_URL=http://127.0.0.1:4000 \
  .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8012
```

Then:

1. upload a supported archive with `POST /api/tasks`
2. confirm `workdir/{task_id}/report_payload.json` exists
3. call `POST /api/tasks/{task_id}/render-report`
4. confirm `outputs/{task_id}/report.docx` exists and opens as a DOCX file

## Input Bundle V1

The current parser support is now formalized in:

- `docs/input_bundle_spec_v1.md`

Recommended archive layout after extraction:

```text
<bundle-root>/
  system/
    system_info
    systemctl_status
  containers/
    docker_ps
```

The current parser prefers these canonical v1 paths first and only keeps a
narrow legacy fallback for older local fixtures.

## Development Rules

- Every new feature, bugfix, or scoped change must start with a plan file under `plans/`.
- Plan naming format: `YYYY-MM-DD-short-name.md`
- Code changes should stay within a single clear small loop.
- After each independent requirement:
  - verify locally
  - commit changes
  - push to GitHub
- Update `docs/project_status.md` every time a scoped requirement is completed.

## Current Scope

Completed:
- project bootstrap
- FastAPI skeleton
- health check endpoint

Planned next:
- `POST /api/tasks`
- zip upload to `uploads/`
- auto-extract to `workdir/{task_id}/`
- task metadata response
- unified JSON output contract for future parsers
