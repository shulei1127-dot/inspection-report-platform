# Xray Collector v2 Plan

## Goal

Improve the existing `xray-collector` adapter in two narrow, high-value areas exposed
by the first real-sample integration:

1. improve Docker table parsing when `PORTS` is empty or whitespace columns are unstable
2. extract `last_boot_at` from a low-ambiguity xray source

## Scope

This iteration only covers:

- Docker row parsing compatibility
- minimal `last_boot_at` extraction
- test updates
- one real-sample remote integration validation pass

This iteration does not cover:

- new service sources
- broader collector framework work
- platform main-flow changes
- unified-json contract changes

## Minimal Strategy

### Docker Parsing

The current Docker parser loses rows when `docker ps -a` output has blank `PORTS`
columns and column alignment shifts.

For v2:

- keep the existing parser contract
- improve `_parse_docker_ps(...)` to prefer header-position parsing for standard
  Docker table output
- retain the older whitespace/tab fallback for non-standard inputs

### last_boot_at

The real xray sample contains:

- `system-logs/list-boot.txt`

This file includes a current boot start timestamp from `journalctl --list-boot`.
That is a low-ambiguity source and is sufficient for v2.

For v2:

- extract current boot start time from boot index `0`
- only accept a clearly parseable timestamp
- normalize it to UTC ISO 8601
- if parsing is unclear, keep current fallback behavior

## Validation

Add or update tests for:

- Docker rows with empty `PORTS`
- xray fixture container coverage improvement
- xray fixture `last_boot_at`
- legal fallback when `last_boot_at` is absent

Run:

- `python3 -m compileall app tests log-analyzer-service/app log-analyzer-service/tests`
- `.venv/bin/pytest`
- `cd log-analyzer-service && ../.venv/bin/pytest`
