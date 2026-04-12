# 2026-04-12 Host Issue V2 Uptime And Last Boot Consistency

## Goal

Add one more small layer of host issue logic based on the relationship between
`uptime_seconds` and `last_boot_at`, without turning the parser into a complex
host diagnostics engine.

## Scope

In scope:
- extend the existing host issue flow only
- add consistency checks between `uptime_seconds` and `last_boot_at`
- keep `unified-json/v1` compatible
- keep summary logic mostly unchanged

Out of scope:
- NTP diagnosis
- timezone drift analysis
- performance or capacity checks
- new log types
- parser refactor

## Minimal Rules

Add host issues when:

1. `uptime_seconds` exists but `last_boot_at` is missing
2. `last_boot_at` exists but `uptime_seconds` is missing
3. `uptime_seconds` is invalid:
   - negative
   - zero
   - clearly abnormal high value
4. `last_boot_at` is later than the parser generation time

## Time Baseline Assumption

This loop uses `generated_at` as a conservative task/parse-time proxy.

That does **not** mean the original log collection time is known exactly, but it
is still safe enough for one narrow consistency rule:

- `last_boot_at > generated_at` is treated as invalid, because a boot time in the
  future relative to parse time is not expected in normal input.

No broader clock-skew logic is introduced.

## Uptime Validity Assumption

Keep the invalid-value rule intentionally simple:

- `uptime_seconds < 0` -> invalid
- `uptime_seconds == 0` -> invalid
- `uptime_seconds > 315360000` (10 years) -> invalid

This threshold is only used as a clearly abnormal sanity check.

## Severity Policy

Keep host consistency issues simple:

- missing counterpart issues -> `low`
- invalid uptime value -> `low`
- future `last_boot_at` -> `medium`

## Validation Plan

1. add coverage for `uptime_seconds` without `last_boot_at`
2. add coverage for `last_boot_at` without `uptime_seconds`
3. add coverage for negative, zero, and abnormal uptime values
4. add coverage for `last_boot_at > generated_at`
5. run full test suite
