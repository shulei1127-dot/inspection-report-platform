# 2026-04-11 Real Carbone Adapter And Render Validation

## Goal

Complete one MVP-sized closed loop for real report rendering:
- keep using the single fixed template `templates/inspection_report.docx`
- use the existing `report_payload.json` as the only rendering input
- try to generate `outputs/{task_id}/report.docx` through a real Carbone runtime
- if runtime setup fails, keep the adapter runnable and return structured failures without faking success

## Chosen Integration Strategy

### Candidate options

1. Local Carbone executable
2. Dockerized Carbone on-premise runtime
3. Carbone Cloud / remote service

### Chosen option for this iteration

Use a local Dockerized Carbone runtime as the primary approach.

Why this is the smallest viable option here:
- Docker is already installed locally
- no existing local `carbone` executable is available in `PATH`
- the current repository already has a fixed local template file
- the official HTTP API supports `POST /render/template?download=true`, which allows direct rendering from a local template file and JSON payload without introducing template storage logic

### Official behavior relied on

From Carbone official documentation:
- the HTTP API is shared between Cloud and On-Premise
- on-premise authentication is disabled by default once the service starts
- `POST /render/template?download=true` supports a base64-encoded template and JSON data in one request

## Expected Runtime Shape

Use a local Carbone container reachable at a configurable base URL.

Default assumptions for this iteration:
- base URL: `http://127.0.0.1:4000`
- health endpoint: `GET /status`
- render endpoint: `POST /render/template?download=true`

## Planned Implementation

1. Extend the rendering service with a real Carbone adapter.
2. Read `report_payload.json` from disk and validate it with `ReportPayloadV1`.
3. Read `templates/inspection_report.docx` from disk.
4. Base64-encode the template and send the render request to Carbone.
5. If rendering succeeds, persist bytes to `outputs/{task_id}/report.docx`.
6. If rendering fails, return structured errors such as:
   - `carbone_unreachable`
   - `carbone_status_failed`
   - `carbone_render_failed`
   - `template_missing`
   - `invalid_report_payload`

## Render Entry Choice

Use a dedicated endpoint for the easiest validation and least risk:

- `POST /api/tasks/{task_id}/render-report`

Why:
- it does not force rendering into the upload happy path
- it is easy to test independently
- it keeps the current upload flow stable

The existing upload flow can keep the optional rendering hook, but the new endpoint will be the primary verification path for this iteration.

## Failure Points To Expect

Possible failure points in the current environment:
- Docker image pull may fail because of network access
- Carbone container may fail to start
- Carbone API may differ from the expected endpoint behavior
- template placeholders may not render as expected
- the default template may be syntactically valid DOCX but still incompatible with real Carbone table-loop processing

If any of these occur:
- keep the adapter boundary intact
- keep returning structured errors
- do not pretend that `report.docx` was generated

## Minimal Contract Adjustments

No unified JSON contract changes are planned.
No report payload contract redesign is planned.

The current temporary `customer_name -> host.hostname` mapping stays as-is and is not part of this iteration.

## Validation Plan

1. Verify the Carbone runtime health check
2. Run unit tests for explicit failure branches
3. If Docker runtime is reachable, run at least one real render path:
   - create/upload task
   - call `POST /api/tasks/{task_id}/render-report`
   - verify `outputs/{task_id}/report.docx` exists and is non-empty
4. If the runtime is not reachable, record the exact failure and keep tests focused on the adapter error path
