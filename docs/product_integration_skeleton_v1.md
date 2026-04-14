# Product Integration Skeleton v1

## Goal

This document defines the first minimal extension skeleton for supporting multiple
log-producing products and their corresponding report templates.

The purpose of v1 is to establish the seams early without introducing a broad
collector framework or expanding parser coverage too aggressively.

## Core Concepts

### `product_type`

`product_type` is the analyzer-side classification of the uploaded product family.

It exists so the system can:

- route analysis to the correct parser adapter
- keep future parser growth inside `log-analyzer-service`
- select the appropriate DOCX template in the platform

### Current v1 Values

- `xray`
- `unknown`

`unknown` is the safe fallback for any input that does not match a supported
product-specific rule.

## Analyzer-Side Recognition

The analyzer owns `product_type` recognition.

For v1, recognition is intentionally rule-based and explainable:

- `xray`
  - recognized when the source directory matches the currently supported
    `xray-collector` shape documented in
    [xray_collector_input_spec_v1.md](/Users/shulei/Downloads/AI/codex/inspection-report-platform/docs/xray_collector_input_spec_v1.md)
- `unknown`
  - used when no product-specific rule matches

v1 does not attempt fuzzy or heuristic-heavy classification.

## Analyzer Parser Routing

Routing is centralized in the analyzer service rather than scattered across
parser entrypoints.

Current v1 routing:

- `xray` -> `XrayCollectorParser`
- `unknown` -> `LinuxDefaultParser`

This keeps the routing seam stable while allowing the actual parser adapters to
stay product-specific.

## Parser Output Expectations

Regardless of parser route, the analyzer still returns:

- `analyze-response/v1`
- inner `unified-json/v1`

For v1, parsed results should carry:

- top-level analyzer `product_type`
- `result.metadata.product_type`
- `result.metadata.parser_route`

This gives the platform enough information to make downstream decisions without
changing the unified JSON contract shape.

## Platform Template Selection

The platform now uses a minimal product-to-template convention.

Current v1 mapping:

- `xray` -> `templates/inspection_report.docx`
- `unknown` -> `templates/inspection_report.docx`

This intentionally reuses the existing default template asset.

The goal of v1 is to establish the selection mechanism, not to introduce a real
multi-template asset set yet.

## Current Flow

1. Upload archive through platform
2. Extract into `workdir/{task_id}/`
3. Platform calls analyzer
4. Analyzer detects `product_type`
5. Analyzer routes to the matching parser
6. Analyzer returns `analyze-response/v1`
7. Platform persists `unified.json`
8. Platform maps to `report_payload.json`
9. Platform resolves template path from `product_type`
10. Platform optionally renders `report.docx`

## Supported Product Specs In v1

- `xray`
  - [xray_collector_input_spec_v1.md](/Users/shulei/Downloads/AI/codex/inspection-report-platform/docs/xray_collector_input_spec_v1.md)
- `unknown`
  - falls back to the canonical input bundle v1 expectation

## Non-Goals

v1 does not include:

- second product parser implementation
- multi-template asset rollout
- dynamic template discovery
- archive upload directly into analyzer
- generic plugin-based collector framework

## What A Second Product Will Need Later

When the second product is introduced, the intended work pattern is:

1. document the product input spec
2. add one product-specific parser adapter
3. add one recognition rule in the analyzer router
4. add one template mapping entry in the platform
5. validate the existing upload -> analyze -> payload -> report chain still holds
