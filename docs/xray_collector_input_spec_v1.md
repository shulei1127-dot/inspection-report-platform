# Xray Collector Input Spec v1

## Purpose

This document defines the first minimal `xray-collector` input shape supported by
`log-analyzer-service`.

The goal of v1 is narrow and practical:

- recognize one real xray collector family already seen in local samples
- normalize that input into the existing canonical parser inputs
- reuse the current `linux_default_parser`
- avoid introducing a broad collector framework too early

## Boundary

`xray-collector` support is analyzer-side normalization only.

The analyzer does not treat xray as a new unified JSON contract. Instead it converts
supported xray files into the existing canonical inputs:

- `system/system_info`
- `system/systemctl_status`
- `containers/docker_ps`

After normalization, the analyzer continues to produce the normal
`unified-json/v1` result.

## Supported Root Layout

v1 supports either:

1. the requested `source.path` itself being the xray root
2. one top-level child directory under `source.path` being the xray root

Typical supported layout:

```text
<source-root>/
  xray-collector.<timestamp>/
    system-logs/
      hostnamectl.txt
      timedatectl.txt
      uname.txt
      uptime.txt
      systemctl-failed.txt
    resource-snapshots/
      docker-ps-a.txt
    network/
      ip-addr.txt
```

The xray root may also be the `source.path` directly.

## Minimal Supported Files

### Host Inputs

Preferred files:

- `system-logs/hostnamectl.txt`
- `system-logs/timedatectl.txt`
- `system-logs/uname.txt`
- `system-logs/uptime.txt`

Optional low-ambiguity boot-time file:

- `system-logs/list-boot.txt`

Optional IP files:

- `network/ip-addr.txt`
- `system-logs/ip.addr.txt`

### Service Inputs

Supported file:

- `system-logs/systemctl-failed.txt`

v1 only extracts failed services from this file. It does not reconstruct a full
`systemctl list-units --type=service --all` inventory.

### Container Inputs

Preferred file:

- `resource-snapshots/docker-ps-a.txt`

Fallback file:

- `xray-logs/container-logs/docker_ps.log`

## Mapping To Canonical Inputs

### `system/system_info`

The adapter builds `system/system_info` from the xray files above.

Current v1 field mapping:

- `hostname`:
  - preferred from `hostnamectl.txt`
  - fallback from `uname.txt`
- `pretty_name`:
  - from `hostnamectl.txt`
- `kernel`:
  - preferred from `hostnamectl.txt`
  - fallback from `uname.txt`
- `timezone`:
  - from `timedatectl.txt`
- `uptime_seconds`:
  - converted from shell-style `uptime` output
- `last_boot_at`:
  - extracted from `journalctl --list-boot` output in `list-boot.txt`
  - only when boot index `0` has a clearly parseable UTC start time
- `ip`:
  - first non-loopback IPv4 address found in `ip-addr.txt` / `ip.addr.txt`

### `system/systemctl_status`

The adapter converts `systemctl-failed.txt` into a minimal canonical status table
containing only failed rows. This is enough for the current issue-generation rules.

### `containers/docker_ps`

The adapter strips xray collector comment preamble lines and writes a canonical
Docker table that the existing Docker parser can read.

## Minimal Format Assumptions

v1 intentionally supports a narrow set of formats:

- `hostnamectl.txt` follows normal `hostnamectl` output
- `timedatectl.txt` follows normal `timedatectl` output
- `uname.txt` contains one `uname -a` style line after optional comment lines
- `uptime.txt` contains one shell `uptime` style line after optional comment lines
- `systemctl-failed.txt` contains `systemctl --failed --no-pager` style rows
- `docker-ps-a.txt` / `docker_ps.log` contains `docker ps -a` style tabular output

## What v1 Produces

This adapter is only expected to support the current minimum useful analyzer output:

- `host_info`
- `services`
- `containers`
- rule-based `issues`
- normal `summary`

## Out Of Scope

v1 does not support:

- archive upload directly into analyzer
- multi-collector routing framework
- every xray file under `system-logs/`, `xray-logs/`, or `container-logs/`
- deep Xray application-specific diagnosis
- AI analysis

## Relationship To Canonical Input Bundle v1

If a collector can be changed, the preferred long-term direction is still to emit the
canonical input bundle directly:

- `system/system_info`
- `system/systemctl_status`
- `containers/docker_ps`

This xray adapter exists so the analyzer can consume one real collector shape now,
without waiting for all collectors to be rewritten.

## Real Validation Notes

This v1 shape has been validated against one real local sample:

- `xray-collector.20260413123039`

The validation confirmed:

- `hostnamectl.txt`, `timedatectl.txt`, `uname.txt`, `uptime.txt` were normalized successfully
- `list-boot.txt` now provides a low-ambiguity `last_boot_at` when the current boot line is parseable
- `systemctl-failed.txt` produced failed-service output and service issues
- `docker-ps-a.txt` produced usable container rows for the current parser and remained
  compatible with downstream `report_payload.json` and DOCX rendering

Follow-up limitation still observed after v2 improvements:

- standard Docker rows with empty `PORTS` are now handled more reliably, but the
  parser still targets standard table output and does not yet cover every possible
  collector-specific variation
