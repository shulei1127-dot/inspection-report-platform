# 2026-04-12 System Info Extension And Host Issue V1

## Goal

Extend `system_info` parsing so `host_info` becomes more complete, then add a
small set of explainable host-level issues based on missing key host facts.

This loop only covers:

1. host field extraction from `system_info`
2. minimal host issue generation for missing host facts

## Scope

In scope:
- extend `system_info` parsing for `ip`, `timezone`, `uptime_seconds`, `last_boot_at`
- keep existing parser structure intact
- reuse the existing `issues[]` generation flow
- keep `unified-json/v1` valid
- keep report payload contract unchanged

Out of scope:
- complex host diagnosis
- performance analysis
- time drift detection
- new log types
- database integration

## Minimal `system_info` Format Assumptions

Assume `system_info` is UTF-8 text with key-value lines separated by `=` or `:`.

This iteration supports these keys:

- hostname:
  - `hostname`
  - `static hostname`
- OS:
  - `pretty_name`
  - `os`
  - `os_name`
  - `name`
  - `os_version`
  - `version`
  - `version_id`
- kernel:
  - `kernel`
  - `kernel_version`
- IP:
  - `ip`
  - `ip_address`
  - `primary_ip`
- timezone:
  - `timezone`
  - `time_zone`
  - `tz`
- uptime:
  - `uptime_seconds`
  - `uptime`
- last boot:
  - `last_boot_at`
  - `last_boot_time`
  - `booted_at`

### Supported uptime input forms

This iteration supports these minimal uptime formats:

- integer seconds
  - `uptime_seconds=86400`
  - `uptime=86400`
- short duration tokens
  - `uptime=1d 2h 3m 4s`
  - `uptime=2h 15m`
- word-based duration tokens
  - `uptime=1 day 2 hours 3 minutes 4 seconds`

If uptime exists but cannot be parsed into seconds, it stays `null` and
produces a host issue.

### Supported last-boot input forms

This iteration supports:

- UTC / offset-aware ISO-like strings
  - `last_boot_at=2026-04-12T08:30:00Z`
  - `last_boot_time=2026-04-12 08:30:00+08:00`

If the value is not parseable, keep `last_boot_at = null`.
This loop does not emit a dedicated issue for unparseable last-boot values.

## Host Issue Rules

Generate a host issue when:

- no explicit hostname was parsed from `system_info`
- `kernel_version` is missing
- `timezone` is missing
- `uptime_seconds` is missing or uptime text was present but unparseable

Severity stays intentionally simple:

- all host completeness issues -> `low`

Category:

- use `host`

## Summary Rules

Do not redesign the existing summary model.
Keep the current overall-status behavior:

- `warning` if any issue exists
- `healthy` if parser has runtime data and no issue exists
- `unknown` if there is no relevant parsed runtime data

Host issues therefore can move the overall status to `warning`.

## Validation Plan

1. extend fixtures with richer `system_info`
2. verify `ip`, `timezone`, `uptime_seconds`, and `last_boot_at`
3. verify host issues for missing hostname, kernel, timezone, and uptime
4. verify fallback still produces legal `unified.json`
5. run full test suite
