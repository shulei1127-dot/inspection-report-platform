# Xray Collector v3 Plan

## Goal

Add a minimal service inventory source for `xray-collector` so `services[]` is no
longer limited to failed-only output.

## Scope

This iteration only covers:

- one minimal service inventory source from the current real xray sample
- small analyzer-side normalization changes
- merge/deduplication with the existing failed-service source
- one real remote integration validation pass

This iteration does not cover:

- additional host diagnostics
- more collector families
- platform main-flow changes
- broad service schema expansion

## Candidate Source

Use:

- `minion-logs/minion-service-status.txt`

Reason:

- it is present in the current real xray sample
- it provides a stable `systemctl status minion --no-pager` output
- it gives one known-running service inventory row without adding broad ambiguity

## Merge Strategy

Normalize two sources into canonical `system/systemctl_status` rows:

1. inventory row from `minion-service-status.txt`
2. failed rows from `systemctl-failed.txt`

Deduplicate by unit name:

- failed row wins if the same service appears in both sources
- otherwise keep both

## Validation

- analyzer tests:
  - xray fixture service count increases
  - running inventory service is preserved
  - failed service is still preserved
- real sample remote integration:
  - compare service count before/after
  - confirm `report_payload.json` compatibility remains intact
