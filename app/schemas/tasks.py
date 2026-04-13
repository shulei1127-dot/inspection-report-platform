from typing import Literal, TypeAlias

from pydantic import BaseModel, Field, model_validator


TaskStatus: TypeAlias = Literal[
    "analyzing",
    "analyze_failed",
    "completed",
    "render_failed",
    "rendered",
    "processing",
    "failed",
]


class TaskCreateOptions(BaseModel):
    parser_profile: str = "default"
    report_lang: str = "zh-CN"


class TaskCleanupOptions(BaseModel):
    keep_latest: int | None = Field(default=None, ge=0)
    older_than_days: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_cleanup_filter(self) -> "TaskCleanupOptions":
        if self.keep_latest is None and self.older_than_days is None:
            raise ValueError("At least one cleanup filter must be provided.")
        return self


class TaskSummary(BaseModel):
    service_count: int = 0
    container_count: int = 0
    issue_count: int = 0


class TaskCreateData(BaseModel):
    task_id: str
    status: Literal["completed", "render_failed", "rendered"]
    contract_version: str = "task-response/v1"
    filename: str
    parser_profile: str
    report_lang: str
    stored_zip_path: str
    workdir_path: str
    unified_json_path: str | None = None
    report_payload_path: str | None = None
    report_file_path: str | None = None
    summary: TaskSummary = Field(default_factory=TaskSummary)


class TaskCreateSuccessResponse(BaseModel):
    success: Literal[True] = True
    data: TaskCreateData


class TaskResultData(BaseModel):
    task_id: str
    status: TaskStatus
    contract_version: str = "task-response/v1"
    created_at: str | None = None
    unified_json_path: str | None = None
    report_payload_path: str | None = None
    report_file_path: str | None = None
    summary: TaskSummary = Field(default_factory=TaskSummary)


class TaskResultSuccessResponse(BaseModel):
    success: Literal[True] = True
    data: TaskResultData


class TaskListSuccessResponse(BaseModel):
    success: Literal[True] = True
    data: list[TaskResultData]


class TaskDeleteData(BaseModel):
    task_id: str
    deleted: Literal[True] = True
    deleted_paths: list[str] = Field(default_factory=list)


class TaskDeleteSuccessResponse(BaseModel):
    success: Literal[True] = True
    data: TaskDeleteData


class TaskCleanupData(BaseModel):
    scanned_count: int = 0
    deleted_count: int = 0
    skipped_count: int = 0
    deleted_task_ids: list[str] = Field(default_factory=list)


class TaskCleanupSuccessResponse(BaseModel):
    success: Literal[True] = True
    data: TaskCleanupData


class RenderReportData(BaseModel):
    task_id: str
    template_path: str
    report_payload_path: str
    report_file_path: str
    renderer: str
    status: Literal["rendered"]


class RenderReportSuccessResponse(BaseModel):
    success: Literal[True] = True
    data: RenderReportData


class TaskError(BaseModel):
    code: str
    message: str
    details: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class TaskErrorResponse(BaseModel):
    success: Literal[False] = False
    error: TaskError
