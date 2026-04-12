## Goal

Add a minimal cleanup capability for filesystem-backed tasks by introducing `DELETE /api/tasks/{task_id}`.

## Scope

- Delete only exact task-owned artifacts derived from `task_id`
- Keep the current file-based task model
- Do not introduce a database
- Do not change parser or report generation behavior

## Exact Paths To Clean

- `uploads/{task_id}.zip`
- `workdir/{task_id}/`
- `outputs/{task_id}/`

## Safety Rules

- Resolve all paths from existing settings and `task_id`
- Do not use globbing or fuzzy matching
- Return `404` when no task artifacts exist

## Implementation Steps

1. Extend task schemas with a delete response model.
2. Add a task service method that resolves task paths, checks existence, and removes exact artifacts.
3. Expose `DELETE /api/tasks/{task_id}` in the tasks endpoint module.
4. Add endpoint tests for successful deletion and missing-task behavior.
5. Update project status and README if needed.
6. Run compile and pytest validation.
