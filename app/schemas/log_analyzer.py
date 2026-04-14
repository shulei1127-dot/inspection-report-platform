from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.unified_json import UnifiedJsonV1

ProductType = Literal["xray", "unknown"]


class AnalyzeDirectorySource(BaseModel):
    type: Literal["directory"] = "directory"
    path: str


class AnalyzeRequestV1(BaseModel):
    request_version: Literal["analyze-request/v1"] = "analyze-request/v1"
    task_id: str
    source: AnalyzeDirectorySource
    archive_name: str | None = None
    archive_size_bytes: int | None = Field(default=None, ge=0)


class AnalyzeInputSummary(BaseModel):
    source_type: Literal["directory"] = "directory"
    path: str
    file_count: int = 0
    directory_count: int = 0


class AnalyzeResponseV1(BaseModel):
    response_version: Literal["analyze-response/v1"] = "analyze-response/v1"
    schema_version: Literal["unified-json/v1"] = "unified-json/v1"
    product_type: ProductType
    analyzer_version: str
    analysis_started_at: str
    analysis_finished_at: str
    warnings: list[str] = Field(default_factory=list)
    input_summary: AnalyzeInputSummary | None = None
    result: UnifiedJsonV1


class AnalyzeErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class AnalyzeErrorResponse(BaseModel):
    success: Literal[False] = False
    error: AnalyzeErrorBody
