## Goal

Add a minimal batch cleanup capability for local trial environments through `POST /api/tasks/cleanup`.

## Scope

- Keep the implementation database-aware but reuse the existing exact-path deletion logic
- Do not introduce schedulers, cron jobs, or automatic background cleanup
- Do not add new database tables

## Supported Cleanup Filters

- `keep_latest`
- `older_than_days`

Both filters are protective:

- `keep_latest` keeps the newest N safe tasks
- `older_than_days` only allows deleting tasks older than the given day threshold
- If both are provided, a task must pass both delete conditions before it is removed

## Safe Statuses

Only tasks in these statuses are eligible for cleanup:

- `rendered`
- `completed`
- `failed`

Tasks in `processing` must always be skipped.

## Deletion Behavior

For each selected task, cleanup must stay aligned with single-task deletion:

- remove `archive_path`
- remove `workdir_path`
- remove `outputs/{task_id}` / `report_file_path`
- remove the matching database record

Deletion must continue to use exact task-derived paths only.

## Return Shape

The batch cleanup response should include at least:

- `scanned_count`
- `deleted_count`
- `skipped_count`
- `deleted_task_ids`

## Implementation Steps

1. Add cleanup request and response schemas.
2. Add a batch cleanup service that scans current task records/results and applies the minimal retention filters.
3. Reuse `delete_task(task_id)` for actual file and database removal.
4. Add `POST /api/tasks/cleanup`.
5. Add tests for `keep_latest`, `older_than_days`, `processing` protection, and synchronized file/database deletion.
6. Update README and project status.
7. Run compile and pytest verification.
