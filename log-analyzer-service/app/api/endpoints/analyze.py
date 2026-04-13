from fastapi import APIRouter, HTTPException

from app.schemas.analyze import AnalyzeRequestV1, AnalyzeResponseV1, ErrorResponse


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
        501: {"model": ErrorResponse},
    },
)
async def analyze_logs(request: AnalyzeRequestV1) -> AnalyzeResponseV1:  # pragma: no cover
    raise HTTPException(
        status_code=501,
        detail={
            "success": False,
            "error": {
                "code": "not_implemented",
                "message": "Analyzer business logic has not been implemented in this scaffold yet.",
                "details": {
                    "request_version": request.request_version,
                    "source_type": request.source.type,
                },
            },
        },
    )
