## Task

Add a minimal multi-product integration skeleton:

- analyzer-side `product_type` recognition
- analyzer-side parser routing
- platform-side template selection convention

## Goal

Define the extension points for future product log onboarding without expanding parser coverage broadly or refactoring the main upload/report flow.

## Scope

1. Introduce `product_type` with a narrow v1 set:
   - `xray`
   - `unknown`
2. Centralize parser routing in analyzer service.
3. Add a minimal product-to-template mapping in the platform.
4. Keep the current default template asset and report flow.

## Assumptions

- v1 recognition must stay rule-based and explainable.
- `xray` detection can rely on the already-supported xray directory/file shape.
- `unknown` is the safe fallback for canonical input bundle v1 and any unrecognized source.
- Template mapping is a mechanism decision in this round, not a multi-template asset rollout.

## Implementation Plan

1. Add analyzer-side `product_type` contract support.
2. Add a centralized product router in `log-analyzer-service`.
3. Route:
   - `xray` -> `XrayCollectorParser`
   - `unknown` -> `LinuxDefaultParser`
4. Ensure parsed results carry `metadata.product_type`.
5. Add a minimal platform template selector:
   - `xray` -> `templates/inspection_report.docx`
   - `unknown` -> `templates/inspection_report.docx`
6. Use the selector in both:
   - upload-flow optional render
   - `POST /api/tasks/{task_id}/render-report`
7. Add tests for:
   - xray recognition
   - unknown fallback
   - router behavior
   - template selection compatibility
8. Update docs and status notes.

## Non-Goals

- no second product parser implementation
- no multi-template asset expansion
- no analyzer archive upload mode
- no platform workflow redesign
