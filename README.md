# Inspection Report Platform

`inspection-report-platform` is a FastAPI-based backend for log package ingestion, parsing, and inspection report generation.

This repository currently contains the MVP bootstrap:
- FastAPI backend skeleton
- `GET /health` health check
- Project conventions and baseline documentation

The upload task flow (`POST /api/tasks`) is planned for the next iteration and is intentionally not included in this scope.

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

## Carbone Runtime

The repository now includes a real HTTP-based Carbone adapter and a dedicated render endpoint:

- `POST /api/tasks/{task_id}/render-report`

The current MVP keeps one fixed template:

- `templates/inspection_report.docx`

The preferred local reproduction path is Docker-based Carbone On-Premise:

```bash
docker run -t -i --rm -p 4000:4000 carbone/carbone-ee:latest
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
- The default shell environment used in this repository may not be able to reach Docker Hub. If the Carbone image cannot be pulled or the runtime cannot be reached, the backend returns structured render errors and does not fake `report.docx` generation.

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
