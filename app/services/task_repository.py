import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

from app.core.config import get_settings


@dataclass(frozen=True)
class TaskRecord:
    task_id: str
    status: str
    created_at: str
    updated_at: str
    archive_path: str | None
    workdir_path: str | None
    unified_json_path: str | None
    report_payload_path: str | None
    report_file_path: str | None
    error_code: str | None
    error_message: str | None


def create_task_record(
    *,
    task_id: str,
    status: str,
    archive_path: str | None,
    workdir_path: str | None,
    unified_json_path: str | None = None,
    report_payload_path: str | None = None,
    report_file_path: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> TaskRecord:
    timestamp = _utc_now_iso()

    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO tasks (
                task_id,
                status,
                created_at,
                updated_at,
                archive_path,
                workdir_path,
                unified_json_path,
                report_payload_path,
                report_file_path,
                error_code,
                error_message
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                status,
                timestamp,
                timestamp,
                archive_path,
                workdir_path,
                unified_json_path,
                report_payload_path,
                report_file_path,
                error_code,
                error_message,
            ),
        )

    return get_task_record(task_id)  # pragma: no cover


def update_task_record(task_id: str, **fields: str | None) -> TaskRecord | None:
    if not fields:
        return get_task_record(task_id)

    existing = get_task_record(task_id)
    if existing is None:
        return None

    column_names = list(fields.keys()) + ["updated_at"]
    values = [fields[name] for name in fields] + [_utc_now_iso(), task_id]
    assignments = ", ".join(f"{column_name} = ?" for column_name in column_names)

    with _connect() as connection:
        connection.execute(
            f"UPDATE tasks SET {assignments} WHERE task_id = ?",
            values,
        )

    return get_task_record(task_id)


def get_task_record(task_id: str) -> TaskRecord | None:
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT
                task_id,
                status,
                created_at,
                updated_at,
                archive_path,
                workdir_path,
                unified_json_path,
                report_payload_path,
                report_file_path,
                error_code,
                error_message
            FROM tasks
            WHERE task_id = ?
            """,
            (task_id,),
        ).fetchone()

    if row is None:
        return None

    return _row_to_task_record(row)


def list_task_records() -> list[TaskRecord]:
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT
                task_id,
                status,
                created_at,
                updated_at,
                archive_path,
                workdir_path,
                unified_json_path,
                report_payload_path,
                report_file_path,
                error_code,
                error_message
            FROM tasks
            ORDER BY created_at DESC, task_id DESC
            """
        ).fetchall()

    return [_row_to_task_record(row) for row in rows]


def delete_task_record(task_id: str) -> bool:
    with _connect() as connection:
        cursor = connection.execute(
            "DELETE FROM tasks WHERE task_id = ?",
            (task_id,),
        )
    return cursor.rowcount > 0


def _connect() -> sqlite3.Connection:
    settings = get_settings()
    settings.tasks_db_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(settings.tasks_db_path)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            archive_path TEXT,
            workdir_path TEXT,
            unified_json_path TEXT,
            report_payload_path TEXT,
            report_file_path TEXT,
            error_code TEXT,
            error_message TEXT
        )
        """
    )
    return connection


def _row_to_task_record(row: sqlite3.Row) -> TaskRecord:
    return TaskRecord(
        task_id=row["task_id"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        archive_path=row["archive_path"],
        workdir_path=row["workdir_path"],
        unified_json_path=row["unified_json_path"],
        report_payload_path=row["report_payload_path"],
        report_file_path=row["report_file_path"],
        error_code=row["error_code"],
        error_message=row["error_message"],
    )


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
