from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse

from app.schemas.tasks import TaskCreateOptions, TaskCreateSuccessResponse, TaskErrorResponse
from app.services.task_service import TaskUploadError, create_task_from_upload


router = APIRouter()


@router.post(
    "/api/tasks",
    response_model=TaskCreateSuccessResponse,
    status_code=201,
    summary="Create an inspection task from a zip upload",
    responses={
        400: {"model": TaskErrorResponse},
        415: {"model": TaskErrorResponse},
        500: {"model": TaskErrorResponse},
    },
)
async def create_task(
    file: UploadFile | None = File(default=None),
    parser_profile: str = Form("default"),
    report_lang: str = Form("zh-CN"),
) -> TaskCreateSuccessResponse | JSONResponse:
    options = TaskCreateOptions(
        parser_profile=parser_profile,
        report_lang=report_lang,
    )

    try:
        data = create_task_from_upload(file, options)
    except TaskUploadError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_response().model_dump(),
        )

    return TaskCreateSuccessResponse(data=data)
