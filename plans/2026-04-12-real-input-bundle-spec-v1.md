# 2026-04-12 Real Input Bundle Spec V1

## Goal

Turn the currently implied parser assumptions into an explicit input-bundle
specification so real users know how to prepare a supported zip file.

## Scope

In scope:
- define a formal input bundle v1 document
- fix the recommended directory layout
- fix the canonical file names
- align parser lookup order with the spec
- align fixtures and tests with the spec

Out of scope:
- new log types
- parser architecture refactor
- broader format loosening
- database or frontend work

## Proposed Input Bundle V1

Recommended zip layout after extraction:

```text
<bundle-root>/
  system/
    system_info
    systemctl_status
  containers/
    docker_ps
```

Canonical file names:

- `system/system_info`
- `system/systemctl_status`
- `containers/docker_ps`

All three files are optional for v1 parsing.
Missing files must keep the output valid and fall back to defaults.

## Compatibility Policy

To avoid breaking the already-working code path too abruptly:

- parser should prefer the canonical v1 paths first
- parser may keep a narrow fallback to exact legacy file names
- do not add more alternative names or formats in this loop

## Minimal Format Rules

### `system/system_info`

- UTF-8 text
- one key-value per line
- separator: `=` or `:`
- supported keys remain the currently implemented set only

### `system/systemctl_status`

- UTF-8 text
- `systemctl list-units --type=service --all --no-pager`-like rows
- one service row per line

### `containers/docker_ps`

- UTF-8 text
- table with `NAMES`, `IMAGE`, `STATUS`
- optional `PORTS`
- tab-separated format remains the recommended stable format

## Validation Plan

1. add a v1 fixture tree using the canonical directories
2. update parser lookup to prefer canonical spec paths
3. verify v1 fixture parses correctly
4. verify missing files still fall back legally
5. verify malformed content stays predictable and does not break the contract
