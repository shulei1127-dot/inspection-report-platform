# 2026-04-12 Carbone Runtime Troubleshooting And First Render

## Goal

Unblock the local Carbone runtime first, then verify one real end-to-end DOCX render:

1. start a local Carbone container
2. confirm the runtime health endpoint is reachable
3. generate a task via `POST /api/tasks`
4. confirm `workdir/{task_id}/report_payload.json` exists
5. call `POST /api/tasks/{task_id}/render-report`
6. verify `outputs/{task_id}/report.docx` is a real DOCX file

## Scope

This loop is intentionally limited to runtime troubleshooting and render verification.

In scope:
- Docker runtime checks
- Docker Hub reachability checks
- proxy, DNS, and platform compatibility checks
- minimal Carbone container startup attempts
- one real render verification if the runtime becomes available
- minimal documentation updates needed for reproducibility

Out of scope:
- real log parsing
- database integration
- multi-template support
- refactoring the upload or render business flow

## Current Assumptions

- FastAPI upload flow already works and can produce `report_payload.json`
- the current HTTP adapter should be kept unless a render verification proves it is wrong
- the default template remains `templates/inspection_report.docx`
- the current environment may still have outbound network issues to Docker Hub

## Troubleshooting Checklist

1. verify Docker daemon and client are healthy
2. verify image pull behavior for `carbone/carbone-ee`
3. check whether `--platform linux/amd64` is required on this host
4. inspect Docker configuration for proxy settings and registry mirrors
5. test DNS and TCP reachability for `registry-1.docker.io:443` and related endpoints
6. if image pull succeeds, run Carbone and probe `GET /status`
7. if runtime is healthy, execute a real render validation through the existing FastAPI endpoints

## Minimal Fix Policy

Only apply a code or config change if it is required to complete the real render validation.
Do not change the business flow unless the failure is clearly inside the adapter or its immediate configuration.

## Stop Conditions

Stop and report clearly if:
- Docker Hub remains unreachable from this shell environment
- the container starts but Carbone itself is unhealthy
- the container is healthy but rendering fails due to template, payload, or adapter issues

In each case, keep the conclusion evidence-based and do not claim render success unless `outputs/{task_id}/report.docx` is truly generated and validated as a DOCX file.
