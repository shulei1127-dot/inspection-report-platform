# 2026-04-11 Default DOCX Template Asset

## Goal

Add one real default DOCX template asset at `templates/inspection_report.docx` and verify that it is compatible with the current MVP `report_payload.json` contract.

This iteration focuses on the template file itself, not on real Carbone rendering success.

## Source Template Choice

Use the local file below as the temporary source/prototype:

- `/Users/shulei/Downloads/洞鉴巡检报告新版.docx`

Reason:
- it is a real existing inspection-report DOCX
- it is closer to the requested "洞鉴巡检报告" prototype direction
- it already contains document styles and real report structure, so the generated project template will be a real document asset rather than an empty placeholder shell

## Scope

In scope:
- design a minimal mapping from current `ReportPayloadV1` to template placeholders
- create `templates/inspection_report.docx`
- keep the template compatible with current stub payload shape
- add tests for default template existence and rendering-service template detection
- update `docs/project_status.md`

Out of scope:
- multi-template routing
- template selection logic
- real Carbone rendering success
- large payload contract redesign

## Minimal Mapping Design

Use the following template-to-payload mapping:

- report title: `d.report.title`
- task id: `d.report.task_id`
- customer/inspection object: temporary map to `d.host.hostname`
- report time: `d.report.generated_at`
- inspect time: temporary map to `d.report.generated_at`
- overall status: `d.summary.overall_status_label`
- summary counts:
  - `d.summary.service_count`
  - `d.summary.service_running_count`
  - `d.summary.container_count`
  - `d.summary.container_running_count`
  - `d.summary.issue_count`
- services table: `d.service_rows[]`
- containers table: `d.container_rows[]`
- issues table: `d.issue_rows[]`

## Required Compatibility Note

Current `ReportPayloadV1` does not contain an explicit `customer_name` field.

For this MVP template only:
- use `d.host.hostname` as the temporary equivalent of customer/inspection object
- do not change the payload contract just for template convenience

This keeps the payload contract stable while still allowing the DOCX template to render a meaningful cover/basic info section.

## Template Design Constraints

1. Prefer compatibility over visual polish.
2. Keep one fixed default template path:
   - `templates/inspection_report.docx`
3. Ensure the document contains real Carbone placeholders for:
   - scalar fields
   - repeated service rows
   - repeated container rows
   - repeated issue rows
4. Keep the template easy to replace later when multi-template support arrives.

## Generation Approach

Because the repository currently has no editable DOCX source asset and binary files are awkward to patch manually:
- copy the chosen source DOCX
- rewrite the body content with a small Python script
- preserve the result as a real `.docx` file under `templates/`

## Validation Plan

1. Verify `templates/inspection_report.docx` exists
2. Verify it is a valid DOCX archive
3. Verify template placeholders for current payload fields are present
4. Verify the rendering service detects template existence and advances beyond the missing-template check

## Risks

- Carbone loop tags inside DOCX tables must remain syntactically consistent
- the temporary `customer_name -> host.hostname` mapping must stay documented so it can be replaced later without confusion
