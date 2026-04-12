import re
from datetime import UTC, datetime
from pathlib import Path

from app.schemas.unified_json import (
    HostInfo,
    IssueBySeverity,
    UnifiedJsonContainer,
    UnifiedJsonParser,
    UnifiedJsonService,
    UnifiedJsonSource,
    UnifiedJsonSummary,
    UnifiedJsonV1,
)

SYSTEM_INFO_NAMES = {"system_info", "system_info.txt", "system_info.log"}
SYSTEMCTL_STATUS_NAMES = {
    "systemctl_status",
    "systemctl_status.txt",
    "systemctl_status.log",
}
DOCKER_PS_NAMES = {"docker_ps", "docker_ps.txt", "docker_ps.log"}


def build_unified_json(
    task_id: str,
    extracted_dir: Path,
    *,
    archive_name: str | None = None,
    archive_size_bytes: int | None = None,
) -> UnifiedJsonV1:
    file_count, dir_count = _scan_extracted_dir(extracted_dir)

    system_info_path = _find_input_file(extracted_dir, SYSTEM_INFO_NAMES)
    systemctl_status_path = _find_input_file(extracted_dir, SYSTEMCTL_STATUS_NAMES)
    docker_ps_path = _find_input_file(extracted_dir, DOCKER_PS_NAMES)

    hostname_fallback = _derive_hostname(extracted_dir, archive_name)
    host_info = _parse_host_info(system_info_path, hostname_fallback=hostname_fallback)
    services = _parse_systemctl_status(systemctl_status_path)
    containers = _parse_docker_ps(docker_ps_path)

    return UnifiedJsonV1(
        schema_version="unified-json/v1",
        task_id=task_id,
        generated_at=_utc_now_isoformat(),
        source=UnifiedJsonSource(
            archive_name=archive_name,
            archive_size_bytes=archive_size_bytes,
            collected_at=None,
        ),
        parser=UnifiedJsonParser(
            name="default-linux-parser",
            version="0.2.0",
        ),
        host_info=host_info,
        summary=_build_summary(services, containers),
        services=services,
        containers=containers,
        issues=[],
        warnings=_build_warnings(
            system_info_path=system_info_path,
            systemctl_status_path=systemctl_status_path,
            docker_ps_path=docker_ps_path,
        ),
        metadata={
            "extracted_file_count": file_count,
            "extracted_directory_count": dir_count,
            "parsed_system_info": system_info_path is not None,
            "parsed_systemctl_status": systemctl_status_path is not None,
            "parsed_docker_ps": docker_ps_path is not None,
        },
    )


def build_unified_json_stub(
    task_id: str,
    extracted_dir: Path,
    *,
    archive_name: str | None = None,
    archive_size_bytes: int | None = None,
) -> UnifiedJsonV1:
    return build_unified_json(
        task_id,
        extracted_dir,
        archive_name=archive_name,
        archive_size_bytes=archive_size_bytes,
    )


def persist_unified_json(unified_json: UnifiedJsonV1, target_path: Path) -> None:
    target_path.write_text(
        unified_json.model_dump_json(indent=2),
        encoding="utf-8",
    )


def _scan_extracted_dir(extracted_dir: Path) -> tuple[int, int]:
    file_count = 0
    dir_count = 0

    for path in extracted_dir.rglob("*"):
        if path.is_file():
            file_count += 1
        elif path.is_dir():
            dir_count += 1

    return file_count, dir_count


def _find_input_file(extracted_dir: Path, names: set[str]) -> Path | None:
    candidates = sorted(
        path
        for path in extracted_dir.rglob("*")
        if path.is_file() and path.name.lower() in names
    )
    if candidates:
        return candidates[0]

    stem_candidates = sorted(
        path
        for path in extracted_dir.rglob("*")
        if path.is_file() and path.stem.lower() in {Path(name).stem for name in names}
    )
    if stem_candidates:
        return stem_candidates[0]

    return None


def _parse_host_info(system_info_path: Path | None, *, hostname_fallback: str) -> HostInfo:
    if system_info_path is None:
        return HostInfo(
            hostname=hostname_fallback,
            ip=None,
            os_name=None,
            os_version=None,
            kernel_version=None,
            timezone=None,
            uptime_seconds=None,
            last_boot_at=None,
        )

    content = system_info_path.read_text(encoding="utf-8", errors="ignore")
    kv = _parse_key_value_text(content)

    hostname = (
        kv.get("hostname")
        or kv.get("static hostname")
        or hostname_fallback
    )
    pretty_name = kv.get("pretty_name") or kv.get("pretty name") or kv.get("os")
    os_name = kv.get("os_name") or kv.get("name")
    os_version = kv.get("os_version") or kv.get("version") or kv.get("version_id")
    kernel_version = kv.get("kernel") or kv.get("kernel_version")

    if not os_name and pretty_name:
        os_name = pretty_name

    if os_name and not os_version and pretty_name:
        pretty_name_lower = pretty_name.lower()
        os_name_lower = os_name.lower()
        if pretty_name_lower.startswith(os_name_lower):
            remainder = pretty_name[len(os_name) :].strip(" -")
            if remainder:
                os_version = remainder

    return HostInfo(
        hostname=hostname or hostname_fallback,
        ip=None,
        os_name=os_name,
        os_version=os_version,
        kernel_version=kernel_version,
        timezone=None,
        uptime_seconds=None,
        last_boot_at=None,
    )


def _parse_key_value_text(content: str) -> dict[str, str]:
    values: dict[str, str] = {}

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        match = re.match(r"^([A-Za-z0-9 _.-]+)\s*[:=]\s*(.+?)\s*$", line)
        if not match:
            continue

        key = match.group(1).strip().lower()
        value = _clean_value(match.group(2))
        if value:
            values[key] = value

    return values


def _parse_systemctl_status(systemctl_status_path: Path | None) -> list[UnifiedJsonService]:
    if systemctl_status_path is None:
        return []

    services: list[UnifiedJsonService] = []

    for raw_line in systemctl_status_path.read_text(
        encoding="utf-8",
        errors="ignore",
    ).splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("UNIT ", "LOAD ", "Legend:", "0 loaded units")):
            continue
        if line.endswith(" loaded units listed.") or line.endswith("loaded units listed."):
            continue

        match = re.match(
            r"^([A-Za-z0-9_.:@-]+\.service)\s+(\S+)\s+(\S+)\s+(\S+)(?:\s+(.*\S))?$",
            line,
        )
        if not match:
            continue

        unit_name = match.group(1)
        active_state = match.group(3).lower()
        sub_state = match.group(4).lower()
        description = match.group(5) or None

        services.append(
            UnifiedJsonService(
                name=unit_name.removesuffix(".service"),
                display_name=description,
                status=_map_service_status(active_state, sub_state),
                enabled=None,
                version=None,
                listen_ports=[],
                start_mode="systemd",
                notes=None,
            )
        )

    return services


def _map_service_status(active_state: str, sub_state: str) -> str:
    if active_state == "failed" or sub_state == "failed":
        return "failed"
    if active_state == "active":
        return "running"
    if active_state in {"inactive", "deactivating"} or sub_state in {"dead", "exited"}:
        return "stopped"
    return "unknown"


def _parse_docker_ps(docker_ps_path: Path | None) -> list[UnifiedJsonContainer]:
    if docker_ps_path is None:
        return []

    lines = docker_ps_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    if not lines:
        return []

    splitter = _pick_table_splitter(lines[0])
    header = splitter(lines[0])
    if not header:
        return []

    header_map = {value.upper(): index for index, value in enumerate(header)}
    required = {"NAMES", "IMAGE", "STATUS"}
    if not required.issubset(header_map):
        return []

    ports_index = header_map.get("PORTS")
    containers: list[UnifiedJsonContainer] = []

    for raw_line in lines[1:]:
        line = raw_line.strip()
        if not line:
            continue

        columns = splitter(raw_line.rstrip())
        required_width = max(header_map[name] for name in required) + 1
        if len(columns) < required_width:
            continue

        name = columns[header_map["NAMES"]].strip()
        image = columns[header_map["IMAGE"]].strip()
        status_text = columns[header_map["STATUS"]].strip()
        ports_text = columns[ports_index].strip() if ports_index is not None and len(columns) > ports_index else ""

        if not name:
            continue

        containers.append(
            UnifiedJsonContainer(
                name=name,
                image=image or None,
                status=_map_container_status(status_text),
                runtime="docker",
                ports=_parse_ports(ports_text),
                restart_policy=None,
                notes=None,
            )
        )

    return containers


def _pick_table_splitter(header_line: str):
    if "\t" in header_line:
        return lambda line: [part.strip() for part in line.split("\t")]
    return lambda line: [part.strip() for part in re.split(r"\s{2,}", line.strip())]


def _map_container_status(status_text: str) -> str:
    value = status_text.lower()
    if value.startswith("up"):
        return "running"
    if "restarting" in value or "dead" in value:
        return "failed"
    if "exited" in value or "created" in value:
        return "stopped"
    return "unknown"


def _parse_ports(ports_text: str) -> list[str]:
    if not ports_text:
        return []
    return [part.strip() for part in ports_text.split(",") if part.strip()]


def _build_summary(
    services: list[UnifiedJsonService],
    containers: list[UnifiedJsonContainer],
) -> UnifiedJsonSummary:
    return UnifiedJsonSummary(
        overall_status="unknown",
        service_count=len(services),
        service_running_count=sum(service.status == "running" for service in services),
        container_count=len(containers),
        container_running_count=sum(
            container.status == "running" for container in containers
        ),
        issue_count=0,
        issue_by_severity=IssueBySeverity(
            critical=0,
            high=0,
            medium=0,
            low=0,
            info=0,
        ),
    )


def _build_warnings(
    *,
    system_info_path: Path | None,
    systemctl_status_path: Path | None,
    docker_ps_path: Path | None,
) -> list[str]:
    warnings = [
        "Real parser v1 only covers system_info, systemctl_status, and docker_ps; unsupported fields still fall back to defaults.",
    ]

    missing_inputs = []
    if system_info_path is None:
        missing_inputs.append("system_info")
    if systemctl_status_path is None:
        missing_inputs.append("systemctl_status")
    if docker_ps_path is None:
        missing_inputs.append("docker_ps")

    if missing_inputs:
        warnings.append(
            "Missing parser inputs fell back to defaults: " + ", ".join(missing_inputs) + "."
        )

    return warnings


def _derive_hostname(extracted_dir: Path, archive_name: str | None) -> str:
    if archive_name:
        stem = Path(archive_name).stem.strip()
        if stem:
            return stem

    top_level_dirs = sorted(
        path.name
        for path in extracted_dir.iterdir()
        if path.is_dir() and path.name.strip()
    )
    if len(top_level_dirs) == 1:
        return top_level_dirs[0]

    top_level_files = sorted(
        path.stem
        for path in extracted_dir.iterdir()
        if path.is_file() and path.stem.strip()
    )
    if len(top_level_files) == 1:
        return top_level_files[0]

    return "unknown-host"


def _clean_value(value: str) -> str:
    return value.strip().strip("'\"")


def _utc_now_isoformat() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
