## Goal

Add minimal support for uploading `.tar.gz` and `.tgz` log archives through the existing `POST /api/tasks` flow.

## Scope

- Keep the same upload endpoint
- Support:
  - `.zip`
  - `.tar.gz`
  - `.tgz`
- Reuse the same extraction -> parse -> unified JSON -> report payload pipeline

## Contract Note

The current response field name `stored_zip_path` is kept for compatibility in this iteration.
Its value will now store the actual uploaded archive path, even when the file is a `.tar.gz` or `.tgz`.

## Safety Rules

- Validate the archive based on the detected archive type
- Keep path traversal protection for both zip and tar archives
- Continue deleting only exact task-specific artifact paths

## Implementation Steps

1. Add archive type detection helpers.
2. Update upload validation to accept `.zip`, `.tar.gz`, and `.tgz`.
3. Store the uploaded archive using the original supported extension.
4. Add safe extraction support for tar archives.
5. Update fallback upload discovery to recognize all supported archive suffixes.
6. Add tests for `.tar.gz` success and updated unsupported-file behavior.
7. Update docs to say "archive" or list the supported formats explicitly.
