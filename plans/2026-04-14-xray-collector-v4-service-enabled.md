## Task

xray-collector v4: supplement minimal `service enabled` extraction.

## Goal

Improve xray-collector parsing so `services[]` can carry a minimal `enabled` value for stable service inventory sources, while keeping the existing platform flow and unified-json contract unchanged.

## Scope

1. Reuse the existing xray adapter and linux default parser.
2. Extract `enabled` from a low-ambiguity xray source.
3. Keep failed service handling intact.
4. Revalidate with the real xray sample in remote analyzer mode.

## Input Assumption

For v4, the only new `enabled` source is:

- `minion-logs/minion-service-status.txt`

The file is assumed to come from `systemctl status <service> --no-pager` and include a `Loaded:` line like:

- `Loaded: loaded (...; enabled; vendor preset: enabled)`
- or `Loaded: loaded (...; disabled; vendor preset: enabled)`

If the enablement token is not clearly present, parsing must fall back to `enabled = null`.

## Implementation Plan

1. Update `xray_collector_parser.py`
   - Extract `enabled` from `minion-service-status.txt`.
   - Materialize the detected value into the canonical `systemctl_status` row using a minimal inline marker.
2. Update `linux_default_parser.py`
   - Parse the inline marker from canonical service descriptions.
   - Strip the marker from `display_name`.
   - Populate `UnifiedJsonService.enabled`.
3. Add tests
   - xray fixture test should assert `minion.enabled is True`.
   - Add a direct parser/API test that canonical `systemctl_status` with the inline marker yields `enabled`.
4. Re-run local tests and a real remote xray integration.

## Notes

- No unified-json contract change is planned.
- No platform main-flow change is planned.
- No archive source work is included.
