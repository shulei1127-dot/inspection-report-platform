# 2026-04-11 Carbone Official Alignment Check

## Goal

Check the current Carbone integration against official Carbone documentation and repository guidance, then make only the smallest corrections needed to align with the official contract.

This iteration is not about forcing a successful render at all costs. If the local environment still cannot start or reach Carbone, keep the adapter honest and document the blocking point clearly.

## Scope

In scope:
- inspect the current Carbone-related implementation
- compare it against official Carbone documentation and repository guidance
- verify:
  - Docker runtime guidance
  - health check / runtime availability check
  - HTTP render endpoint path and request shape
  - template transfer format
  - report payload submission format
  - same-format DOCX output expectations and LibreOffice requirements
  - template placeholder and loop syntax compatibility
- apply only minimal fixes for confirmed mismatches
- update project docs with the aligned guidance

Out of scope:
- real log parsing
- database integration
- multi-template design
- payload contract redesign

## Files To Inspect

- `app/services/report_rendering_service.py`
- `app/api/endpoints/tasks.py`
- `templates/inspection_report.docx`
- `.env.example`
- `README.md`

## Expected Official Source Priorities

Use only official Carbone sources where possible:
- official documentation pages
- official GitHub repository

## Minimal-Fix Policy

Only change code or template behavior when the mismatch is confirmed by official documentation.

Examples of acceptable minimal fixes:
- correcting endpoint paths
- correcting request body fields
- correcting health-check behavior
- correcting template loop markers if they are inconsistent with official syntax
- clarifying Docker startup guidance in README and `.env.example`

Examples of changes to avoid:
- redesigning the business payload
- introducing multi-template selection
- refactoring unrelated routes or services

## Known Risk Areas To Verify

1. Whether `carbone/carbone-ee:latest` is really the currently recommended public Docker image path
2. Whether `GET /status` is the correct runtime check for on-premise HTTP API
3. Whether `POST /render/template?download=true` is the correct endpoint for base64-template rendering
4. Whether the current request body keys match official expectations
5. Whether DOCX-to-DOCX generation needs LibreOffice
6. Whether the current DOCX template loop rows match official array repetition rules

## Validation Plan

1. Re-run unit tests after any minimal fixes
2. Re-check template placeholders inside `word/document.xml`
3. If runtime is still unreachable, verify the adapter returns explicit structured errors
4. Record the exact environment block if official Docker runtime still cannot be pulled or started
