from pathlib import Path

from app.services.parser_stub import build_unified_json


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "real_parser_v1"


def test_build_unified_json_parses_supported_files(tmp_path: Path) -> None:
    extracted_dir = tmp_path / "extracted"
    extracted_dir.mkdir()

    for fixture_path in sorted(FIXTURE_DIR.iterdir()):
        (extracted_dir / fixture_path.name).write_text(
            fixture_path.read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    unified_json = build_unified_json(
        "tsk_test_real_parser",
        extracted_dir,
        archive_name="fixture.zip",
        archive_size_bytes=321,
    )

    assert unified_json.schema_version == "unified-json/v1"
    assert unified_json.host_info.hostname == "host-a"
    assert unified_json.host_info.os_name == "Ubuntu"
    assert unified_json.host_info.os_version == "22.04.4 LTS (Jammy Jellyfish)"
    assert unified_json.host_info.kernel_version == "5.15.0-105-generic"

    assert [service.name for service in unified_json.services] == [
        "nginx",
        "docker",
        "fail2ban",
        "auditd",
    ]
    assert [service.status for service in unified_json.services] == [
        "running",
        "running",
        "failed",
        "stopped",
    ]
    assert unified_json.services[0].display_name == "A high performance web server"
    assert unified_json.services[0].start_mode == "systemd"

    assert [container.name for container in unified_json.containers] == [
        "redis",
        "worker",
    ]
    assert [container.status for container in unified_json.containers] == [
        "running",
        "stopped",
    ]
    assert unified_json.containers[0].image == "redis:7.2"
    assert unified_json.containers[0].ports == ["0.0.0.0:6379->6379/tcp"]
    assert unified_json.containers[0].runtime == "docker"

    assert unified_json.summary.overall_status == "unknown"
    assert unified_json.summary.service_count == 4
    assert unified_json.summary.service_running_count == 2
    assert unified_json.summary.container_count == 2
    assert unified_json.summary.container_running_count == 1
    assert unified_json.summary.issue_count == 0
    assert unified_json.parser is not None
    assert unified_json.parser.name == "default-linux-parser"
    assert unified_json.metadata["parsed_system_info"] is True
    assert unified_json.metadata["parsed_systemctl_status"] is True
    assert unified_json.metadata["parsed_docker_ps"] is True


def test_build_unified_json_falls_back_when_supported_inputs_are_missing(
    tmp_path: Path,
) -> None:
    extracted_dir = tmp_path / "extracted"
    extracted_dir.mkdir()
    (extracted_dir / "notes.txt").write_text("hello\n", encoding="utf-8")

    unified_json = build_unified_json(
        "tsk_test_fallback",
        extracted_dir,
        archive_name="fallback-host.zip",
        archive_size_bytes=111,
    )

    assert unified_json.schema_version == "unified-json/v1"
    assert unified_json.host_info.hostname == "fallback-host"
    assert unified_json.host_info.os_name is None
    assert unified_json.host_info.kernel_version is None
    assert unified_json.services == []
    assert unified_json.containers == []
    assert unified_json.summary.service_count == 0
    assert unified_json.summary.container_count == 0
    assert unified_json.parser is not None
    assert unified_json.parser.name == "default-linux-parser"
    assert unified_json.metadata["parsed_system_info"] is False
    assert unified_json.metadata["parsed_systemctl_status"] is False
    assert unified_json.metadata["parsed_docker_ps"] is False
