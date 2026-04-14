# Xray Collector Real Sample Integration v1 Plan

## Goal

Validate the new `xray-collector v1` adapter against one real extracted sample in
remote analyzer mode, then record what already works, what only partially works, and
what should be deferred to v2.

## Scope

This iteration only covers:

- one real `xray-collector` sample
- platform upload in `ANALYZER_MODE=remote`
- generated `unified.json`
- generated `report_payload.json`
- optional report rendering compatibility check when Carbone is available

This iteration does not cover:

- new parser rules
- xray adapter v2
- platform main-flow refactors
- report contract changes

## Real Sample Choice

Use the richer local sample already present in the repository workdir:

- `workdir/tsk_20260413_094550_ef166b1d/xray-collector.20260413123039`

Reason:

- it includes the exact v1-supported files:
  - `system-logs/hostnamectl.txt`
  - `system-logs/timedatectl.txt`
  - `system-logs/uname.txt`
  - `system-logs/uptime.txt`
  - `system-logs/systemctl-failed.txt`
  - `resource-snapshots/docker-ps-a.txt`
  - `network/ip-addr.txt`

## Validation Steps

1. Package the real sample into a temporary archive without changing its contents
2. Start `log-analyzer-service`
3. Start platform in `ANALYZER_MODE=remote`
4. Upload the archive through `POST /api/tasks`
5. Inspect generated:
   - `unified.json`
   - `report_payload.json`
6. If Carbone is reachable, optionally render `report.docx`

## Expected Focus

Check:

- `host_info`
- `services`
- `containers`
- `issues`
- `summary`

Record:

- which fields parsed correctly
- which fields are still missing
- which xray files were matched by v1 rules
- which gaps should stay for v2

## Possible Minimal Doc Updates

- `docs/project_status.md`
- `docs/xray_collector_input_spec_v1.md`
- `README.md` only if the real validation exposes a user-facing caveat worth noting
