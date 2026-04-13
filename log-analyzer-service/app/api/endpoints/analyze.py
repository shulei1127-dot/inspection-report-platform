from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.schemas.analyze import AnalyzeRequestV1, AnalyzeResponseV1, ErrorResponse
from app.services.analyzer_service import AnalyzerServiceError, build_analyzer_service


router = APIRouter()


@router.post(
    "/analyze",
    response_model=AnalyzeResponseV1,
    summary="Analyze an extracted directory and return unified-json/v1",
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def analyze_logs(request: AnalyzeRequestV1) -> AnalyzeResponseV1 | JSONResponse:
    try:
        response = build_analyzer_service().analyze(request)
    except AnalyzerServiceError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                },
            },
        )

    return response
