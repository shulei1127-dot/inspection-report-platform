from typing import Literal

from pydantic import BaseModel, Field


class TaskCreateOptions(BaseModel):
    parser_profile: str = "default"
    report_lang: str = "zh-CN"


class TaskSummary(BaseModel):
    service_count: int = 0
    container_count: int = 0
    issue_count: int = 0


class TaskCreateData(BaseModel):
    task_id: str
    status: Literal["completed", "failed"]
    contract_version: str = "task-response/v1"
    filename: str
    parser_profile: str
    report_lang: str
    stored_zip_path: str
    workdir_path: str
    unified_json_path: str | None = None
    report_payload_path: str | None = None
    summary: TaskSummary = Field(default_factory=TaskSummary)


class TaskCreateSuccessResponse(BaseModel):
    success: Literal[True] = True
    data: TaskCreateData


class TaskError(BaseModel):
    code: str
    message: str
    details: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class TaskErrorResponse(BaseModel):
    success: Literal[False] = False
    error: TaskError
