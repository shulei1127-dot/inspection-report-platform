import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.schemas.unified_json import (
    HostInfo,
    IssueBySeverity,
    UnifiedJsonContainer,
    UnifiedJsonIssue,
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


@dataclass(frozen=True)
class HostParseResult:
    host_info: HostInfo
    explicit_hostname_found: bool
    uptime_value_present: bool
    uptime_invalid_reason: str | None
    last_boot_value_present: bool


def build_unified_json(
    task_id: str,
    extracted_dir: Path,
    *,
    archive_name: str | None = None,
    archive_size_bytes: int | None = None,
) -> UnifiedJsonV1:
    file_count, dir_count = _scan_extracted_dir(extracted_dir)
    generated_at = _utc_now_isoformat()

    system_info_path = _find_input_file(extracted_dir, SYSTEM_INFO_NAMES)
    systemctl_status_path = _find_input_file(extracted_dir, SYSTEMCTL_STATUS_NAMES)
    docker_ps_path = _find_input_file(extracted_dir, DOCKER_PS_NAMES)

    hostname_fallback = _derive_hostname(extracted_dir, archive_name)
    host_parse_result = _parse_host_info(
        system_info_path,
        hostname_fallback=hostname_fallback,
    )
    host_info = host_parse_result.host_info
    services = _parse_systemctl_status(systemctl_status_path)
    containers = _parse_docker_ps(docker_ps_path)
    issues = _build_issues(
        host_parse_result,
        services,
        containers,
        generated_at=generated_at,
    )

    return UnifiedJsonV1(
        schema_version="unified-json/v1",
        task_id=task_id,
        generated_at=generated_at,
        source=UnifiedJsonSource(
            archive_name=archive_name,
            archive_size_bytes=archive_size_bytes,
            collected_at=None,
        ),
        parser=UnifiedJsonParser(
            name="default-linux-parser",
            version="0.5.0",
        ),
        host_info=host_info,
        summary=_build_summary(services, containers, issues),
        services=services,
        containers=containers,
        issues=issues,
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


def _parse_host_info(
    system_info_path: Path | None,
    *,
    hostname_fallback: str,
) -> HostParseResult:
    if system_info_path is None:
        return HostParseResult(
            host_info=HostInfo(
                hostname=hostname_fallback,
                ip=None,
                os_name=None,
                os_version=None,
                kernel_version=None,
                timezone=None,
                uptime_seconds=None,
                last_boot_at=None,
            ),
            explicit_hostname_found=False,
            uptime_value_present=False,
            uptime_invalid_reason=None,
            last_boot_value_present=False,
        )

    content = system_info_path.read_text(encoding="utf-8", errors="ignore")
    kv = _parse_key_value_text(content)

    hostname_value = kv.get("hostname") or kv.get("static hostname")
    hostname = hostname_value or hostname_fallback
    pretty_name = kv.get("pretty_name") or kv.get("pretty name") or kv.get("os")
    os_name = kv.get("os_name") or kv.get("name")
    os_version = kv.get("os_version") or kv.get("version") or kv.get("version_id")
    kernel_version = kv.get("kernel") or kv.get("kernel_version")
    ip = kv.get("ip") or kv.get("ip_address") or kv.get("primary_ip")
    timezone = kv.get("timezone") or kv.get("time_zone") or kv.get("tz")
    uptime_raw = kv.get("uptime_seconds") or kv.get("uptime")
    uptime_parse = _parse_uptime_seconds(uptime_raw) if uptime_raw else UptimeParseResult(
        seconds=None,
        invalid_reason=None,
    )
    last_boot_raw = (
        kv.get("last_boot_at")
        or kv.get("last_boot_time")
        or kv.get("booted_at")
    )
    last_boot_at = _parse_timestamp(last_boot_raw) if last_boot_raw else None

    if not os_name and pretty_name:
        os_name = pretty_name

    if os_name and not os_version and pretty_name:
        pretty_name_lower = pretty_name.lower()
        os_name_lower = os_name.lower()
        if pretty_name_lower.startswith(os_name_lower):
            remainder = pretty_name[len(os_name) :].strip(" -")
            if remainder:
                os_version = remainder

    return HostParseResult(
        host_info=HostInfo(
            hostname=hostname or hostname_fallback,
            ip=ip,
            os_name=os_name,
            os_version=os_version,
            kernel_version=kernel_version,
            timezone=timezone,
            uptime_seconds=uptime_parse.seconds,
            last_boot_at=last_boot_at,
        ),
        explicit_hostname_found=bool(hostname_value),
        uptime_value_present=uptime_raw is not None,
        uptime_invalid_reason=uptime_parse.invalid_reason,
        last_boot_value_present=last_boot_raw is not None,
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


@dataclass(frozen=True)
class UptimeParseResult:
    seconds: int | None
    invalid_reason: str | None


def _parse_uptime_seconds(value: str) -> UptimeParseResult:
    normalized = value.strip().lower()
    if not normalized:
        return UptimeParseResult(seconds=None, invalid_reason="empty")

    if re.fullmatch(r"-?\d+", normalized):
        return _validate_uptime_seconds(int(normalized))

    compact_matches = re.findall(r"(\d+)\s*([dhms])", normalized)
    if compact_matches:
        total = sum(
            int(amount) * _duration_unit_seconds(unit)
            for amount, unit in compact_matches
        )
        return _validate_uptime_seconds(total)

    word_matches = re.findall(
        r"(\d+)\s*(day|days|hour|hours|minute|minutes|second|seconds)",
        normalized,
    )
    if word_matches:
        total = 0
        for amount, unit in word_matches:
            total += int(amount) * _duration_unit_seconds(unit)
        return _validate_uptime_seconds(total)

    return UptimeParseResult(seconds=None, invalid_reason="unparseable")


def _validate_uptime_seconds(value: int) -> UptimeParseResult:
    if value < 0:
        return UptimeParseResult(seconds=None, invalid_reason="negative")
    if value == 0:
        return UptimeParseResult(seconds=None, invalid_reason="zero")
    if value > 315360000:
        return UptimeParseResult(seconds=None, invalid_reason="too_large")
    return UptimeParseResult(seconds=value, invalid_reason=None)


def _duration_unit_seconds(unit: str) -> int:
    mapping = {
        "d": 86400,
        "day": 86400,
        "days": 86400,
        "h": 3600,
        "hour": 3600,
        "hours": 3600,
        "m": 60,
        "minute": 60,
        "minutes": 60,
        "s": 1,
        "second": 1,
        "seconds": 1,
    }
    return mapping[unit]


def _parse_timestamp(value: str) -> str | None:
    normalized = value.strip()
    if not normalized:
        return None

    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)

    return parsed.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
                notes=f"systemd state: load={match.group(2).lower()} active={active_state} sub={sub_state}",
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
                notes=f"docker status: {status_text}",
            )
        )

    return containers


def _pick_table_splitter(header_line: str):
    if "\t" in header_line:
        return lambda line: [part.strip() for part in line.split("\t")]
    return lambda line: [part.strip() for part in re.split(r"\s{2,}", line.strip())]


def _map_container_status(status_text: str) -> str:
    value = status_text.lower()
    if "unhealthy" in value:
        return "failed"
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
    issues: list[UnifiedJsonIssue],
) -> UnifiedJsonSummary:
    severity_counts = _count_issue_severity(issues)

    return UnifiedJsonSummary(
        overall_status=_derive_overall_status(services, containers, issues),
        service_count=len(services),
        service_running_count=sum(service.status == "running" for service in services),
        container_count=len(containers),
        container_running_count=sum(
            container.status == "running" for container in containers
        ),
        issue_count=len(issues),
        issue_by_severity=severity_counts,
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


def _build_issues(
    host_parse_result: HostParseResult,
    services: list[UnifiedJsonService],
    containers: list[UnifiedJsonContainer],
    *,
    generated_at: str,
) -> list[UnifiedJsonIssue]:
    issues: list[UnifiedJsonIssue] = []

    host_issues = _build_host_issues(
        host_parse_result,
        generated_at=generated_at,
    )
    issues.extend(host_issues)

    for service in services:
        service_issue = _build_service_issue(service)
        if service_issue is not None:
            issues.append(service_issue)

    for container in containers:
        container_issue = _build_container_issue(container)
        if container_issue is not None:
            issues.append(container_issue)

    return issues


def _build_host_issues(
    host_parse_result: HostParseResult,
    *,
    generated_at: str,
) -> list[UnifiedJsonIssue]:
    host_info = host_parse_result.host_info
    issues: list[UnifiedJsonIssue] = []

    if not host_parse_result.explicit_hostname_found:
        issues.append(
            UnifiedJsonIssue(
                id="host-hostname-missing",
                severity="low",
                category="host",
                title="Host hostname is missing",
                description="No explicit hostname could be parsed from system_info.",
                suggestion="Collect hostname information in system_info so the host can be identified reliably.",
                related_object_type="host",
                related_object_name=host_info.hostname,
            )
        )

    if not host_info.kernel_version:
        issues.append(
            UnifiedJsonIssue(
                id="host-kernel-version-missing",
                severity="low",
                category="host",
                title="Host kernel version is missing",
                description="Kernel version could not be parsed from system_info.",
                suggestion="Collect kernel version in system_info for baseline host inspection.",
                related_object_type="host",
                related_object_name=host_info.hostname,
            )
        )

    if not host_info.timezone:
        issues.append(
            UnifiedJsonIssue(
                id="host-timezone-missing",
                severity="low",
                category="host",
                title="Host timezone is missing",
                description="Timezone could not be parsed from system_info.",
                suggestion="Collect timezone information in system_info for report consistency.",
                related_object_type="host",
                related_object_name=host_info.hostname,
            )
        )

    if host_info.uptime_seconds is None:
        description = _build_uptime_missing_description(host_parse_result)
        issues.append(
            UnifiedJsonIssue(
                id=(
                    "host-uptime-invalid"
                    if host_parse_result.uptime_invalid_reason is not None
                    else "host-uptime-missing"
                ),
                severity="low",
                category="host",
                title=(
                    "Host uptime is invalid"
                    if host_parse_result.uptime_invalid_reason is not None
                    else "Host uptime is missing"
                ),
                description=description,
                suggestion="Collect uptime in a supported format such as integer seconds or duration tokens.",
                related_object_type="host",
                related_object_name=host_info.hostname,
            )
        )

    if host_info.uptime_seconds is not None and not host_info.last_boot_at:
        issues.append(
            UnifiedJsonIssue(
                id="host-last-boot-missing",
                severity="low",
                category="host",
                title="Host last boot time is missing",
                description="Uptime was parsed successfully but last_boot_at is missing.",
                suggestion="Collect last boot time in system_info when uptime is available.",
                related_object_type="host",
                related_object_name=host_info.hostname,
            )
        )

    if host_parse_result.last_boot_value_present and host_info.last_boot_at and host_info.uptime_seconds is None:
        issues.append(
            UnifiedJsonIssue(
                id="host-uptime-last-boot-inconsistent",
                severity="low",
                category="host",
                title="Host uptime is missing while last boot time exists",
                description="last_boot_at was parsed successfully but uptime_seconds is missing or invalid.",
                suggestion="Collect both uptime and last boot time in compatible formats.",
                related_object_type="host",
                related_object_name=host_info.hostname,
            )
        )

    if host_info.last_boot_at and _is_future_relative_to_generated_at(
        host_info.last_boot_at,
        generated_at,
    ):
        issues.append(
            UnifiedJsonIssue(
                id="host-last-boot-in-future",
                severity="medium",
                category="host",
                title="Host last boot time is later than task time",
                description="Parsed last_boot_at is later than the parser generation time.",
                suggestion="Check host time settings and the source value collected in system_info.",
                related_object_type="host",
                related_object_name=host_info.hostname,
            )
        )

    return issues


def _build_uptime_missing_description(host_parse_result: HostParseResult) -> str:
    if not host_parse_result.uptime_value_present:
        return "Uptime could not be found in system_info."

    reason = host_parse_result.uptime_invalid_reason
    if reason == "negative":
        return "Uptime was present but the value is negative."
    if reason == "zero":
        return "Uptime was present but the value is zero."
    if reason == "too_large":
        return "Uptime was present but the value is abnormally large."
    return "Uptime was present in system_info but could not be parsed into seconds."


def _is_future_relative_to_generated_at(last_boot_at: str, generated_at: str) -> bool:
    try:
        last_boot_dt = datetime.fromisoformat(last_boot_at.replace("Z", "+00:00"))
        generated_at_dt = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    return last_boot_dt > generated_at_dt


def _build_service_issue(service: UnifiedJsonService) -> UnifiedJsonIssue | None:
    note = (service.notes or "").lower()

    if service.status == "failed":
        return UnifiedJsonIssue(
            id=_make_issue_id("service", service.name, "failed"),
            severity="medium",
            category="service",
            title=f"Service {service.name} is in failed state",
            description=service.notes or "Service was reported by systemd as failed.",
            suggestion=f"Inspect `systemctl status {service.name}` and recover the {service.name} service.",
            related_object_type="service",
            related_object_name=service.name,
        )

    if "active=inactive" in note or "sub=dead" in note:
        return UnifiedJsonIssue(
            id=_make_issue_id("service", service.name, "inactive"),
            severity="low",
            category="service",
            title=f"Service {service.name} is inactive",
            description=service.notes or "Service was reported by systemd as inactive or dead.",
            suggestion=f"Confirm whether {service.name} should be running and start or enable it if required.",
            related_object_type="service",
            related_object_name=service.name,
        )

    return None


def _build_container_issue(container: UnifiedJsonContainer) -> UnifiedJsonIssue | None:
    note = (container.notes or "").lower()

    if "unhealthy" in note:
        return UnifiedJsonIssue(
            id=_make_issue_id("container", container.name, "unhealthy"),
            severity="medium",
            category="container",
            title=f"Container {container.name} is unhealthy",
            description=container.notes or "Container health status was reported as unhealthy.",
            suggestion=f"Inspect the health check and runtime logs for container {container.name}.",
            related_object_type="container",
            related_object_name=container.name,
        )

    if "restarting" in note:
        return UnifiedJsonIssue(
            id=_make_issue_id("container", container.name, "restarting"),
            severity="medium",
            category="container",
            title=f"Container {container.name} is restarting",
            description=container.notes or "Container runtime reported repeated restarts.",
            suggestion=f"Inspect container logs and restart policy for {container.name}.",
            related_object_type="container",
            related_object_name=container.name,
        )

    if "exited" in note:
        return UnifiedJsonIssue(
            id=_make_issue_id("container", container.name, "exited"),
            severity="low",
            category="container",
            title=f"Container {container.name} has exited",
            description=container.notes or "Container runtime reported an exited container.",
            suggestion=f"Confirm whether container {container.name} should be running and restart it if required.",
            related_object_type="container",
            related_object_name=container.name,
        )

    return None


def _count_issue_severity(issues: list[UnifiedJsonIssue]) -> IssueBySeverity:
    counts = {
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "info": 0,
    }

    for issue in issues:
        counts[issue.severity] += 1

    return IssueBySeverity(**counts)


def _derive_overall_status(
    services: list[UnifiedJsonService],
    containers: list[UnifiedJsonContainer],
    issues: list[UnifiedJsonIssue],
) -> str:
    if issues:
        return "warning"
    if services or containers:
        return "healthy"
    return "unknown"


def _make_issue_id(category: str, object_name: str, state: str) -> str:
    safe_name = re.sub(r"[^a-z0-9]+", "-", object_name.lower()).strip("-") or "unknown"
    return f"{category}-{safe_name}-{state}"


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
