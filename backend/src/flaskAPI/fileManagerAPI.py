import os
import sys
from typing import List, Optional

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from werkzeug.utils import secure_filename

# Add parent directory to path to import FileManager
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as cfg  # noqa: E402
from fileUploadManager import FileManager  # noqa: E402
from logging_Setup import get_logger  # noqa: E402

logger = get_logger(__name__)

router = APIRouter()


class DownloadRequest(BaseModel):
    url: Optional[str] = Field(None, description="File URL to download")
    workspace_name: Optional[str] = Field(
        None, description="Workspace name to associate downloaded file with"
    )


file_manager = FileManager()


@router.post("/download")
async def download_file_api(payload: DownloadRequest):
    """
    Download a file from a remote URL into the workspace storage.
    """
    if not payload.url and not payload.workspace_name:
        return JSONResponse(
            content={
                "status": "error",
                "error_type": "missing_parameter",
                "message": "Missing URL parameter",
            },
            status_code=400,
        )

    result = file_manager.download_file_api(payload.url, payload.workspace_name)

    if result.get("status") == "success":
        return JSONResponse(content=result, status_code=200)

    error_status_codes = {
        "file_type_error": 403,
        "file_size_error": 413,
        "download_error": 400,
        "unknown_error": 500,
    }
    status_code = error_status_codes.get(result.get("error_type", "unknown_error"), 400)
    return JSONResponse(content=result, status_code=status_code)


@router.post("/upload")
async def upload_file_api(
    file: Optional[UploadFile] = File(None),
    files: Optional[List[UploadFile]] = File(None),
    workspace_name: Optional[str] = Form(None),
):
    """
    Upload one or more files into the workspace storage.
    Accepts either 'files' (plural) or 'file' (singular) field names.
    """
    # Handle both 'files' (plural) and 'file' (singular) field names
    upload_files = []
    
    if files:
        # Multiple files provided
        upload_files = files if isinstance(files, list) else [files]
        logger.info(f"Received {len(upload_files)} file(s) in 'files' field")
    elif file:
        # Single file provided
        upload_files = [file]
        logger.info(f"Received 1 file in 'file' field: {file.filename}")
    
    if not upload_files:
        logger.warning("Upload request contained no files")
        return JSONResponse(
            content={
                "status": "error",
                "error_type": "missing_file",
                "message": "No files were provided. Please send file(s) with field name 'file' or 'files'",
            },
            status_code=400,
        )

    logger.info(
        f"Processing {len(upload_files)} file(s) for upload "
        f"in workspace: {workspace_name or 'default'}"
    )

    results = []
    errors = []

    for upload in upload_files:
        if not upload.filename:
            logger.warning("Skipping file with empty filename")
            continue

        original_filename = upload.filename
        filename = secure_filename(original_filename)
        ext = os.path.splitext(filename)[1].lower()

        if ext == ".webp":
            filename = f"{os.path.splitext(filename)[0]}.png"
            logger.info(f"Renamed .webp to .png => {filename}")

        if original_filename != filename:
            logger.info(
                f"Sanitized filename from '{original_filename}' to '{filename}'"
            )

        ext = os.path.splitext(filename)[1].lower()
        if ext not in cfg.ALLWOED_EXTENSIONS:
            logger.warning(f"Rejected file '{filename}' with disallowed type: {ext}")
            errors.append(
                {
                    "filename": filename,
                    "error": f"File type {ext} is not allowed",
                    "error_type": "invalid_file_type",
                }
            )
            continue

        if workspace_name:
            save_dir = os.path.join(cfg.UPLOAD_DIR, workspace_name)
            os.makedirs(save_dir, exist_ok=True)
        else:
            save_dir = cfg.UPLOAD_DIR

        file_path = os.path.join(save_dir, filename)
        logger.debug(f"Planned save path: {file_path}")

        if os.path.exists(file_path):
            logger.info(f"File already exists: {file_path}")
            file_details = file_manager.get_file_details(file_path)
            results.append(
                {
                    "filename": filename,
                    "path": file_path,
                    "size": file_details["size_bytes"],
                    "size_human": file_details["size_human"],
                    "already_exists": True,
                }
            )
            continue

        try:
            contents = await upload.read()
            with open(file_path, "wb") as destination:
                destination.write(contents)
            logger.info(f"Successfully saved file: {filename}")
        except Exception as save_error:  # pragma: no cover - I/O failure
            logger.exception(f"Failed to save file {filename}: {str(save_error)}")
            errors.append(
                {
                    "filename": filename,
                    "error": f"Failed to save file: {str(save_error)}",
                    "error_type": "save_error",
                }
            )
            if os.path.exists(file_path):
                os.remove(file_path)
            continue
        finally:
            await upload.close()

        file_details = file_manager.get_file_details(file_path)
        if file_details["size_bytes"] > cfg.MAX_FILE_SIZE_BYTES:
            logger.warning(
                f"File too large: {filename} ({file_details['size_human']})"
            )
            os.remove(file_path)
            errors.append(
                {
                    "filename": filename,
                    "error": (
                        "File size exceeds the maximum limit of "
                        f"{cfg.MAX_FILE_SIZE_BYTES / 1048576:.1f}MB"
                    ),
                    "error_type": "file_too_large",
                }
            )
            continue

        logger.info(
            f"File uploaded successfully: {filename} "
            f"({file_details['size_human']})"
        )
        results.append(
            {
                "filename": filename,
                "path": file_path,
                "size": file_details["size_bytes"],
                "size_human": file_details["size_human"],
                "already_exists": False,
                "mime_type": file_details["mime_type"],
            }
        )

    if results:
        logger.info(
            f"Upload complete: {len(results)} file(s) successful, "
            f"{len(errors)} failure(s)"
        )
        return JSONResponse(
            content={
                "status": "success",
                "message": f"Uploaded {len(results)} file(s) successfully",
                "data": {
                    "uploaded_files": results,
                    "errors": errors,
                    "workspace": workspace_name,
                },
            },
            status_code=200,
        )

    if errors:
        logger.error(f"Upload failed: All {len(errors)} file(s) had errors")
        return JSONResponse(
            content={
                "status": "error",
                "error_type": "upload_failed",
                "message": "All file uploads failed",
                "errors": errors,
            },
            status_code=400,
        )

    logger.warning("Upload request resulted in no files processed")
    return JSONResponse(
        content={
            "status": "error",
            "error_type": "no_files_processed",
            "message": "No files were processed",
        },
        status_code=400,
    )