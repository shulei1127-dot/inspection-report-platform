import io
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_create_task_uploads_and_extracts_zip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    zip_bytes = _build_zip_bytes(
        {
            "logs/system.log": "system ok\n",
            "meta/info.txt": "metadata\n",
        }
    )

    response = client.post(
        "/api/tasks",
        files={"file": ("host-a-logs.zip", zip_bytes, "application/zip")},
        data={"parser_profile": "default", "report_lang": "zh-CN"},
    )

    assert response.status_code == 201

    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["status"] == "completed"
    assert payload["data"]["contract_version"] == "task-response/v1"
    assert payload["data"]["filename"] == "host-a-logs.zip"
    assert payload["data"]["parser_profile"] == "default"
    assert payload["data"]["report_lang"] == "zh-CN"
    assert payload["data"]["summary"] == {
        "service_count": 0,
        "container_count": 0,
        "issue_count": 0,
    }
    assert payload["data"]["unified_json_path"] is None
    assert payload["data"]["report_payload_path"] is None

    task_id = payload["data"]["task_id"]
    stored_zip_path = tmp_path / "uploads" / f"{task_id}.zip"
    extracted_log_path = tmp_path / "workdir" / task_id / "logs" / "system.log"
    extracted_info_path = tmp_path / "workdir" / task_id / "meta" / "info.txt"

    assert stored_zip_path.exists()
    assert extracted_log_path.read_text() == "system ok\n"
    assert extracted_info_path.read_text() == "metadata\n"


def test_create_task_rejects_non_zip_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    response = client.post(
        "/api/tasks",
        files={"file": ("notes.txt", b"not a zip", "text/plain")},
        data={"parser_profile": "default", "report_lang": "zh-CN"},
    )

    assert response.status_code == 415
    assert response.json() == {
        "success": False,
        "error": {
            "code": "unsupported_media_type",
            "message": "Only .zip files are accepted.",
            "details": {
                "filename": "notes.txt",
            },
        },
    }


def test_create_task_requires_file_field(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    response = client.post(
        "/api/tasks",
        data={"parser_profile": "default", "report_lang": "zh-CN"},
    )

    assert response.status_code == 400
    assert response.json() == {
        "success": False,
        "error": {
            "code": "missing_file",
            "message": "No upload file was provided.",
            "details": {},
        },
    }


def _build_zip_bytes(entries: dict[str, str]) -> bytes:
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)

    return buffer.getvalue()
