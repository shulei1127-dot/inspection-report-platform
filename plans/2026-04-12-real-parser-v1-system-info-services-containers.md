# 2026-04-12 Real Parser V1 For System Info, Services, And Containers

## Goal

Replace part of the current parser stub behavior so that `unified.json` starts
including real parsed data from a small set of known input files while keeping
the existing upload flow intact.

This loop only targets:

1. `system_info`
2. `systemctl_status`
3. `docker_ps`

## Scope

In scope:
- reuse the current parser entry used by `POST /api/tasks`
- parse available files into `host_info`, `services`, and `containers`
- keep missing files on stub/default fallback behavior
- keep `unified-json/v1` contract valid
- keep `report_payload.json` generation compatible with the current mapper

Out of scope:
- real issue generation
- AI analysis
- database integration
- multi-template support
- broad parser framework refactor
- support for many more log types

## Minimal Format Assumptions

### `system_info`

Assume `system_info` is a UTF-8 text file and support these minimal patterns:

- key-value lines separated by `=` or `:`
- common keys:
  - `hostname`
  - `static hostname`
  - `os`
  - `os_name`
  - `pretty_name`
  - `name`
  - `os_version`
  - `version`
  - `version_id`
  - `kernel`
  - `kernel_version`

Supported examples:

- `hostname=host-a`
- `static hostname: host-a`
- `PRETTY_NAME="Ubuntu 22.04.4 LTS"`
- `VERSION_ID="22.04"`
- `kernel=5.15.0-105-generic`

If multiple keys exist, prefer the more specific normalized values:

- hostname: `hostname` or `static hostname`
- OS name/version: prefer `PRETTY_NAME`; otherwise combine `NAME` and `VERSION`
- kernel: `kernel` or `kernel_version`

### `systemctl_status`

Assume `systemctl_status` is a UTF-8 text file that contains rows similar to
`systemctl list-units --type=service --all --no-pager`.

Minimal supported pattern per line:

- service unit name ending in `.service`
- followed by service state columns such as:
  - `loaded active running`
  - `loaded inactive dead`
  - `loaded failed failed`
- optional trailing description text

Example:

- `nginx.service loaded active running A high performance web server`

For this first version:

- `name` comes from unit name without `.service`
- `display_name` comes from the trailing description when present
- `status` maps from active/sub state to `running`, `stopped`, `failed`, or `unknown`
- `enabled`, `version`, `listen_ports`, and `start_mode` stay conservative defaults

### `docker_ps`

Assume `docker_ps` is a UTF-8 text table with a header that includes:

- `NAMES`
- `IMAGE`
- `STATUS`
- optional `PORTS`

This version supports two minimal formats:

1. tab-separated table rows
2. rows separated by 2 or more spaces

Recommended collection format for stable parsing:

- `docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'`

For this first version:

- `name`, `image`, `status`, and `ports` are parsed when present
- `runtime` is set to `docker`
- `restart_policy` stays `null`

## Minimal Compatibility Adjustment

To keep the API response aligned with the new parsed result, `POST /api/tasks`
may update its response summary counts from the generated `unified.json`
instead of always returning zero counts.

This is a narrow consistency fix, not a contract change.

## Validation Plan

1. add fixture inputs for the three supported files
2. verify parsed `host_info`, `services`, and `containers`
3. verify missing-file fallback still produces valid `unified.json`
4. verify `report_payload.json` generation still works with parsed data
5. run `pytest`
