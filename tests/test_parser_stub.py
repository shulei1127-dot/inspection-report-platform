from pathlib import Path

from app.services.parser_stub import build_unified_json


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "real_parser_v1"
SPEC_V1_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "input_bundle_spec_v1"


def test_build_unified_json_parses_spec_v1_bundle_layout(tmp_path: Path) -> None:
    extracted_dir = tmp_path / "extracted"
    extracted_dir.mkdir()

    for fixture_path in sorted(path for path in SPEC_V1_FIXTURE_DIR.rglob("*") if path.is_file()):
        target_path = extracted_dir / fixture_path.relative_to(SPEC_V1_FIXTURE_DIR)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(
            fixture_path.read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    unified_json = build_unified_json(
        "tsk_test_spec_v1_bundle",
        extracted_dir,
        archive_name="spec-v1.zip",
        archive_size_bytes=999,
    )

    assert unified_json.host_info.hostname == "host-a"
    assert unified_json.host_info.ip == "10.0.0.8"
    assert [service.name for service in unified_json.services] == [
        "nginx",
        "docker",
        "fail2ban",
        "auditd",
    ]
    assert [container.name for container in unified_json.containers] == [
        "redis",
        "worker",
    ]


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
    assert unified_json.host_info.ip == "10.0.0.8"
    assert unified_json.host_info.os_name == "Ubuntu"
    assert unified_json.host_info.os_version == "22.04.4 LTS (Jammy Jellyfish)"
    assert unified_json.host_info.kernel_version == "5.15.0-105-generic"
    assert unified_json.host_info.timezone == "Asia/Shanghai"
    assert unified_json.host_info.uptime_seconds == 93784
    assert unified_json.host_info.last_boot_at == "2026-04-10T08:30:00Z"

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

    assert unified_json.summary.overall_status == "warning"
    assert unified_json.summary.service_count == 4
    assert unified_json.summary.service_running_count == 2
    assert unified_json.summary.container_count == 2
    assert unified_json.summary.container_running_count == 1
    assert unified_json.summary.issue_count == 3
    assert unified_json.summary.issue_by_severity.medium == 1
    assert unified_json.summary.issue_by_severity.low == 2
    assert [issue.id for issue in unified_json.issues] == [
        "service-fail2ban-failed",
        "service-auditd-inactive",
        "container-worker-exited",
    ]
    assert [issue.severity for issue in unified_json.issues] == [
        "medium",
        "low",
        "low",
    ]
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
    assert unified_json.host_info.timezone is None
    assert unified_json.host_info.uptime_seconds is None
    assert unified_json.services == []
    assert unified_json.containers == []
    assert unified_json.summary.service_count == 0
    assert unified_json.summary.container_count == 0
    assert unified_json.summary.overall_status == "warning"
    assert unified_json.summary.issue_count == 4
    assert [issue.id for issue in unified_json.issues] == [
        "host-hostname-missing",
        "host-kernel-version-missing",
        "host-timezone-missing",
        "host-uptime-missing",
    ]
    assert unified_json.parser is not None
    assert unified_json.parser.name == "default-linux-parser"
    assert unified_json.metadata["parsed_system_info"] is False
    assert unified_json.metadata["parsed_systemctl_status"] is False
    assert unified_json.metadata["parsed_docker_ps"] is False


def test_build_unified_json_generates_unhealthy_container_issue(tmp_path: Path) -> None:
    extracted_dir = tmp_path / "extracted"
    extracted_dir.mkdir()
    (extracted_dir / "system_info").write_text(
        'hostname=host-b\nPRETTY_NAME="Ubuntu 24.04 LTS"\nkernel=6.8.0\ntimezone=UTC\nuptime_seconds=7200\n',
        encoding="utf-8",
    )
    (extracted_dir / "systemctl_status").write_text(
        "UNIT LOAD ACTIVE SUB DESCRIPTION\nnginx.service loaded active running Nginx\n",
        encoding="utf-8",
    )
    (extracted_dir / "docker_ps").write_text(
        "NAMES\tIMAGE\tSTATUS\tPORTS\napi\tnginx:1.27\tUp 2 minutes (unhealthy)\t0.0.0.0:8080->80/tcp\n",
        encoding="utf-8",
    )

    unified_json = build_unified_json(
        "tsk_test_unhealthy_container",
        extracted_dir,
        archive_name="unhealthy.zip",
        archive_size_bytes=222,
    )

    assert unified_json.containers[0].status == "failed"
    assert unified_json.summary.overall_status == "warning"
    assert unified_json.summary.issue_count == 2
    assert [issue.id for issue in unified_json.issues] == [
        "host-last-boot-missing",
        "container-api-unhealthy",
    ]
    assert unified_json.issues[1].severity == "medium"
    assert unified_json.issues[1].category == "container"


def test_build_unified_json_keeps_issues_empty_when_runtime_is_healthy(
    tmp_path: Path,
) -> None:
    extracted_dir = tmp_path / "extracted"
    extracted_dir.mkdir()
    (extracted_dir / "system_info").write_text(
        'hostname=healthy-host\nPRETTY_NAME="Ubuntu 24.04 LTS"\nkernel=6.8.0\ntimezone=UTC\nuptime=2h\nip=10.0.0.20\nlast_boot_at=2026-04-12T00:00:00Z\n',
        encoding="utf-8",
    )
    (extracted_dir / "systemctl_status").write_text(
        "\n".join(
            [
                "UNIT LOAD ACTIVE SUB DESCRIPTION",
                "nginx.service loaded active running Nginx",
                "docker.service loaded active running Docker Engine",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (extracted_dir / "docker_ps").write_text(
        "NAMES\tIMAGE\tSTATUS\tPORTS\nredis\tredis:7.2\tUp 2 hours\t0.0.0.0:6379->6379/tcp\n",
        encoding="utf-8",
    )

    unified_json = build_unified_json(
        "tsk_test_healthy_runtime",
        extracted_dir,
        archive_name="healthy.zip",
        archive_size_bytes=333,
    )

    assert unified_json.summary.overall_status == "healthy"
    assert unified_json.summary.issue_count == 0
    assert unified_json.issues == []


def test_build_unified_json_keeps_output_valid_when_input_format_is_invalid(
    tmp_path: Path,
) -> None:
    extracted_dir = tmp_path / "extracted"
    (extracted_dir / "system").mkdir(parents=True)
    (extracted_dir / "containers").mkdir(parents=True)
    (extracted_dir / "system" / "system_info").write_text(
        "hostname\nPRETTY_NAME Ubuntu 24.04\nkernel\n",
        encoding="utf-8",
    )
    (extracted_dir / "system" / "systemctl_status").write_text(
        "NOT A SYSTEMCTL TABLE\nsomething unexpected\n",
        encoding="utf-8",
    )
    (extracted_dir / "containers" / "docker_ps").write_text(
        "BROKEN HEADER\nsomething unexpected\n",
        encoding="utf-8",
    )

    unified_json = build_unified_json(
        "tsk_test_invalid_bundle_format",
        extracted_dir,
        archive_name="invalid-format.zip",
        archive_size_bytes=1000,
    )

    assert unified_json.schema_version == "unified-json/v1"
    assert unified_json.host_info.hostname == "invalid-format"
    assert unified_json.services == []
    assert unified_json.containers == []
    assert unified_json.summary.issue_count >= 1


def test_build_unified_json_generates_host_issues_for_missing_host_fields(
    tmp_path: Path,
) -> None:
    extracted_dir = tmp_path / "extracted"
    extracted_dir.mkdir()
    (extracted_dir / "system_info").write_text(
        'PRETTY_NAME="Ubuntu 24.04 LTS"\nip=10.10.10.10\nuptime=not-a-duration\n',
        encoding="utf-8",
    )

    unified_json = build_unified_json(
        "tsk_test_host_issues",
        extracted_dir,
        archive_name="host-issues.zip",
        archive_size_bytes=444,
    )

    assert unified_json.host_info.hostname == "host-issues"
    assert unified_json.host_info.ip == "10.10.10.10"
    assert unified_json.host_info.kernel_version is None
    assert unified_json.host_info.timezone is None
    assert unified_json.host_info.uptime_seconds is None
    assert unified_json.summary.overall_status == "warning"
    assert [issue.id for issue in unified_json.issues] == [
        "host-hostname-missing",
        "host-kernel-version-missing",
        "host-timezone-missing",
        "host-uptime-invalid",
    ]
    assert all(issue.category == "host" for issue in unified_json.issues)


def test_build_unified_json_generates_issue_when_uptime_exists_without_last_boot(
    tmp_path: Path,
) -> None:
    extracted_dir = tmp_path / "extracted"
    extracted_dir.mkdir()
    (extracted_dir / "system_info").write_text(
        "\n".join(
            [
                "hostname=host-c",
                "kernel=6.8.0",
                "timezone=UTC",
                "uptime_seconds=3600",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    unified_json = build_unified_json(
        "tsk_test_uptime_without_last_boot",
        extracted_dir,
        archive_name="uptime-only.zip",
        archive_size_bytes=555,
    )

    assert unified_json.host_info.uptime_seconds == 3600
    assert unified_json.host_info.last_boot_at is None
    assert "host-last-boot-missing" in [issue.id for issue in unified_json.issues]


def test_build_unified_json_generates_issue_when_last_boot_exists_without_uptime(
    tmp_path: Path,
) -> None:
    extracted_dir = tmp_path / "extracted"
    extracted_dir.mkdir()
    (extracted_dir / "system_info").write_text(
        "\n".join(
            [
                "hostname=host-d",
                "kernel=6.8.0",
                "timezone=UTC",
                "last_boot_at=2026-04-12T00:00:00Z",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    unified_json = build_unified_json(
        "tsk_test_last_boot_without_uptime",
        extracted_dir,
        archive_name="last-boot-only.zip",
        archive_size_bytes=666,
    )

    issue_ids = [issue.id for issue in unified_json.issues]
    assert unified_json.host_info.last_boot_at == "2026-04-12T00:00:00Z"
    assert "host-uptime-missing" in issue_ids
    assert "host-uptime-last-boot-inconsistent" in issue_ids


def test_build_unified_json_generates_issue_for_invalid_uptime_seconds(
    tmp_path: Path,
) -> None:
    cases = [
        ("-1", "Uptime was present but the value is negative."),
        ("0", "Uptime was present but the value is zero."),
        ("315360001", "Uptime was present but the value is abnormally large."),
    ]

    for index, (uptime_value, expected_description) in enumerate(cases, start=1):
        extracted_dir = tmp_path / f"extracted_{index}"
        extracted_dir.mkdir()
        (extracted_dir / "system_info").write_text(
            "\n".join(
                [
                    "hostname=host-e",
                    "kernel=6.8.0",
                    "timezone=UTC",
                    f"uptime_seconds={uptime_value}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        unified_json = build_unified_json(
            f"tsk_test_invalid_uptime_{index}",
            extracted_dir,
            archive_name="invalid-uptime.zip",
            archive_size_bytes=777,
        )

        issue_ids = [issue.id for issue in unified_json.issues]
        uptime_issue = next(
            issue for issue in unified_json.issues if issue.id == "host-uptime-invalid"
        )

        assert unified_json.host_info.uptime_seconds is None
        assert "host-uptime-invalid" in issue_ids
        assert uptime_issue.description == expected_description


def test_build_unified_json_generates_issue_when_last_boot_is_in_future(
    tmp_path: Path,
) -> None:
    extracted_dir = tmp_path / "extracted"
    extracted_dir.mkdir()
    (extracted_dir / "system_info").write_text(
        "\n".join(
            [
                "hostname=future-host",
                "kernel=6.8.0",
                "timezone=UTC",
                "uptime_seconds=3600",
                "last_boot_at=2999-01-01T00:00:00Z",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    unified_json = build_unified_json(
        "tsk_test_future_last_boot",
        extracted_dir,
        archive_name="future-last-boot.zip",
        archive_size_bytes=888,
    )

    future_issue = next(
        issue for issue in unified_json.issues if issue.id == "host-last-boot-in-future"
    )

    assert unified_json.host_info.last_boot_at == "2999-01-01T00:00:00Z"
    assert future_issue.severity == "medium"
