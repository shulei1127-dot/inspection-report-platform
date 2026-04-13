## Goal

Add a minimal homepage at `/` so the running MVP has a friendly entry point instead of returning `404`.

## Scope

- Add only one small root route
- Do not introduce a frontend framework, template engine, or asset pipeline
- Keep the page informational and link-focused

## Homepage Content

- project name
- one short description
- links to:
  - `/docs`
  - `/health`
  - `/api/tasks`
  - `/openapi.json`

## Implementation Steps

1. Add a small homepage endpoint that returns static HTML.
2. Register the homepage router without affecting existing API routes.
3. Add tests for `/` and keep `/health` coverage intact.
4. Update README and project status.
5. Run compile and pytest verification.
