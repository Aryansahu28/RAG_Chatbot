import os
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as cfg  # noqa: E402
from logging_Setup import get_logger  # noqa: E402

logger = get_logger(__name__)

router = APIRouter()

IMAGE_STORAGE_DIR = Path(cfg.IMAGE_STORAGE_DIR)
UPLOAD_DIR = Path(cfg.UPLOAD_DIR)
OUTPUT_DIR = Path(cfg.OUTPUT_DIR)


def _ensure_safe_path(base: Path, target: str) -> Path:
    base_resolved = base.resolve()
    resolved = (base / target).resolve()
    try:
        resolved.relative_to(base_resolved)
    except ValueError:
        logger.warning(f"Attempted path traversal detected: {target}")
        raise HTTPException(status_code=400, detail="Invalid file path")
    return resolved


@router.get("/images/{filename}")
async def serve_file_from_images(filename: str):
    file_path = _ensure_safe_path(IMAGE_STORAGE_DIR, filename)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)


@router.get("/files/{workspace}/{filename}")
async def serve_file_from_upload_dir_v1(workspace: str, filename: str):
    if not workspace:
        raise HTTPException(status_code=400, detail="Workspace not specified")

    workspace_dir = _ensure_safe_path(UPLOAD_DIR, workspace)
    file_path = workspace_dir / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(file_path)


@router.get("/files/{file_path:path}")
async def serve_file_from_upload_dir_v2(file_path: str):
    full_path = _ensure_safe_path(UPLOAD_DIR, file_path)
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(full_path)


@router.get("/outputfiles/{file_path:path}")
async def serve_file_from_output_dir_path(file_path: str):
    full_path = _ensure_safe_path(OUTPUT_DIR, file_path)
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(full_path)
