# 2026-04-12 Minimal Task List API

## Goal

Add a minimal `GET /api/tasks` endpoint so users can see recent task history
without remembering task IDs manually.

## Scope

In scope:
- `GET /api/tasks`
- file-system based task discovery
- latest-first ordering
- minimal task summary items

Out of scope:
- database persistence
- pagination
- filtering
- search
- parser changes

## Data Source Strategy

Task list is inferred from the existing filesystem state:

- `uploads/{task_id}.zip`
- `workdir/{task_id}/`
- `outputs/{task_id}/`

All discovered task IDs from those locations are merged into one set.

## Ordering Strategy

Preferred sort key:

- parsed timestamp from `task_id`
  - format: `tsk_YYYYMMDD_HHMMSS_<suffix>`

Fallback:

- newest available file/directory modification time

Sort newest first.

## Response Shape

Return a top-level `success` plus `data` list.
Each item should include at least:

- `task_id`
- `status`
- `unified_json_path`
- `report_payload_path`
- `report_file_path`
- `summary`
- `created_at`

## Validation Plan

1. verify multiple tasks are returned
2. verify latest-first ordering
3. verify field structure aligns with current task-result style
