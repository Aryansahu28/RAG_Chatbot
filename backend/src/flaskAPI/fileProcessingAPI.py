import os
import sys
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Add parent directory to path to import process_files_api
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from process_files import generate_image_description, process_files_api  # noqa: E402

router = APIRouter()


class ProcessFileRequest(BaseModel):
    file_path: str = Field(..., description="Path of the file to process")
    image_metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Optional image metadata"
    )
    workspace_name: Optional[str] = Field(
        default=None, description="Optional workspace to associate processing output"
    )


@router.post("/process")
async def process_file_api_route(payload: ProcessFileRequest):
    try:
        result = process_files_api(
            payload.file_path, payload.image_metadata, payload.workspace_name
        )
    except Exception as exc:  # pragma: no cover - underlying handler failure
        return JSONResponse(
            content={
                "status": "error",
                "message": str(exc),
                "error_type": "server_error",
            },
            status_code=500,
        )

    if result.get("status") == "success":
        return JSONResponse(content=result, status_code=200)

    error_status_codes = {
        "file_already_exists": 409,
        "file_too_large": 413,
        "invalid_file_type": 415,
        "file_not_found": 404,
        "processing_failed": 422,
        "unexpected_error": 500,
    }
    status_code = error_status_codes.get(result.get("error_type"), 400)
    return JSONResponse(content=result, status_code=status_code)


@router.get("/generate_image_description")
async def generate_image_description_api(
    image_path: str = Query(..., description="Source image path")
):
    try:
        result = generate_image_description(image_path)
    except Exception as exc:  # pragma: no cover - upstream failure
        return JSONResponse(
            content={
                "status": "error",
                "message": str(exc),
                "error_type": "server_error",
            },
            status_code=500,
        )

    if result:
        return JSONResponse(
            content={"status": "success", "data": result},
            status_code=200,
        )

    return JSONResponse(
        content={
            "status": "error",
            "message": "Failed to generate image description",
            "error_type": "processing_failed",
        },
        status_code=422,
    )