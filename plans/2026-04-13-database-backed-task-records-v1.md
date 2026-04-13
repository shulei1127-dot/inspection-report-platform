## Goal

Introduce a minimal database-backed task record so task lifecycle and history are no longer inferred only from the filesystem.

## Chosen Approach

- Use SQLite via Python standard library `sqlite3`
- Keep a single `tasks` table
- Avoid ORM, migration framework, and multi-table design in this iteration
- Keep existing HTTP contracts stable
- Keep narrow filesystem fallback for pre-database or partially missing local data

## Minimum Table Shape

- `task_id`
- `status`
- `created_at`
- `updated_at`
- `archive_path`
- `workdir_path`
- `unified_json_path`
- `report_payload_path`
- `report_file_path`
- `error_code`
- `error_message`

## Status Handling

- `processing` when a task record is first created
- `completed` after `unified.json` and `report_payload.json` are persisted
- `rendered` after `report.docx` is successfully generated
- `failed` only when a task enters an explicit upload failure after `task_id` has already been created

## Scope Notes

- Summary counts remain file-derived from `unified.json`
- `GET /api/tasks/{task_id}` and `GET /api/tasks` prefer database records
- If no database record exists, keep current filesystem fallback behavior
- `DELETE /api/tasks/{task_id}` removes exact task artifacts and then removes the database record

## Implementation Steps

1. Add a minimal SQLite-backed repository/service for task records with lazy table creation.
2. Add config for the SQLite file path and document it.
3. Write a task record when upload processing starts.
4. Update the record after `unified.json`, `report_payload.json`, and optional `report.docx` generation.
5. Update task detail and task list reads to prefer database-backed records.
6. Update delete flow to remove the database record together with task artifacts.
7. Add endpoint tests that verify upload writes the database row, list/detail read through the database path, and delete removes the record.
8. Update project docs and run local verification.
