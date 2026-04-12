# 2026-04-12 Issue Generation V1 From Services And Containers

## Goal

Add minimal, explainable `issues[]` generation on top of the current real parser
results so that `unified.json` starts containing real findings derived from
parsed `services` and `containers`.

This loop only covers rules based on:

1. parsed service states
2. parsed container states

## Scope

In scope:
- reuse the current parser flow in `app/services/parser_stub.py`
- generate issues from already parsed `services` and `containers`
- update `summary.overall_status`, `issue_count`, and `issue_by_severity`
- keep `unified-json/v1` valid
- keep report payload mapping compatible

Out of scope:
- AI diagnosis
- deep root-cause analysis
- new log types
- parser architecture refactor
- database integration

## Minimal Status Assumptions

### Service issue rules

Generate an issue when the parsed service row indicates one of:

- `failed`
- `inactive`
- `dead`

For this parser version:

- `failed` is detected from `active=failed` or `sub=failed`
- `inactive` / `dead` are detected from the raw `systemctl_status` columns
- normalized service `status` still stays within the contract:
  - `running`
  - `stopped`
  - `failed`
  - `unknown`

### Container issue rules

Generate an issue when the raw Docker status text indicates one of:

- `exited`
- `unhealthy`
- `restarting`

For this parser version:

- `unhealthy` is detected from Docker status text like `Up 2 minutes (unhealthy)`
- `restarting` is detected from status text containing `Restarting`
- `exited` is detected from status text containing `Exited`
- normalized container `status` still stays within the contract

## Contract-Compatible Field Mapping

The user-facing request mentions `level` and `evidence`, but `unified-json/v1`
defines these issue fields instead:

- `severity`
- `description`

So this iteration maps:

- requested `level` -> contract field `severity`
- requested `evidence` -> contract field `description`

No contract change is introduced in this loop.

## Severity And Overall Status Rules

Keep the severity model intentionally simple:

- service `failed` -> `medium`
- service `inactive` / `dead` -> `low`
- container `restarting` / `unhealthy` -> `medium`
- container `exited` -> `low`

Overall status rules:

- `warning` when at least one issue exists
- `healthy` when parser has real service/container data and no issues exist
- `unknown` when no relevant runtime data exists

This loop does not emit `critical`.

## Validation Plan

1. verify failed service produces an issue
2. verify exited container produces an issue
3. verify unhealthy container produces an issue
4. verify healthy inputs keep `issues[]` empty
5. verify `summary.overall_status` changes with issue presence
