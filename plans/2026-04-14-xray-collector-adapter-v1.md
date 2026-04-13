# Xray Collector Adapter v1 Plan

## Goal

Add a minimal `xray-collector` adapter to `log-analyzer-service` so the analyzer can
recognize one real collector layout, normalize it into the existing canonical parser
inputs, and reuse the current `linux_default_parser` without changing the platform
main flow or the unified JSON contract.

## Scope

This iteration only covers:

- xray-collector input recognition
- a narrow adapter layer in `log-analyzer-service`
- reuse of the existing canonical parser for:
  - `system_info`
  - `systemctl_status`
  - `docker_ps`
- one fixed xray fixture
- minimal docs and tests

This iteration explicitly does not cover:

- multi-collector framework design
- archive-upload mode for analyzer
- parser expansion beyond current host/service/container/issue scope
- platform main-flow changes
- report payload or Carbone changes

## Minimal Supported Xray Input

v1 will support a narrow real-world xray layout based on currently observed collector
samples. The adapter will recognize either the requested directory itself or a single
top-level child directory as the xray root.

Supported input files:

- `system-logs/hostnamectl.txt`
- `system-logs/timedatectl.txt`
- `system-logs/uname.txt`
- `system-logs/uptime.txt`
- `system-logs/systemctl-failed.txt`
- `resource-snapshots/docker-ps-a.txt`
- fallback container file: `xray-logs/container-logs/docker_ps.log`
- optional IP source:
  - `network/ip-addr.txt`
  - `system-logs/ip.addr.txt`

## Implementation Shape

1. Add `docs/xray_collector_input_spec_v1.md`
2. Add `log-analyzer-service/app/parsers/xray_collector_parser.py`
3. Detect xray input in `AnalyzerService`
4. Normalize xray files into a temporary canonical tree:
   - `system/system_info`
   - `system/systemctl_status`
   - `containers/docker_ps`
5. Reuse `LinuxDefaultParser.parse(...)` on that canonical tree

## Minimal Field Mapping

- `hostnamectl.txt` + `uname.txt` -> hostname, OS, kernel
- `timedatectl.txt` -> timezone
- `uptime.txt` -> `uptime_seconds`
- `ip-addr.txt` / `ip.addr.txt` -> `ip` when present
- `systemctl-failed.txt` -> failed services only
- `docker-ps-a.txt` / `docker_ps.log` -> containers

`last_boot_at` is intentionally not added in v1 unless a stable canonical source is
available. The existing host issue logic can safely keep reporting last-boot missing.

## Tests

Add/extend analyzer tests to cover:

- xray input recognition
- valid `analyze-response/v1`
- valid `unified-json/v1` result
- expected parsed hostname / timezone / IP
- expected service and container counts

## Verification

- `python3 -m compileall app tests log-analyzer-service/app log-analyzer-service/tests`
- `.venv/bin/pytest`
- `cd log-analyzer-service && ../.venv/bin/pytest`
