import os
import sys
from typing import Dict, Generator, Union

from fastapi import APIRouter, Depends, Path
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as cfg  # noqa: E402
from database import Database  # noqa: E402
from delete_document import delete_file_api, delete_workspace_api  # noqa: E402
from logging_Setup import get_logger  # noqa: E402

logger = get_logger(__name__)

router = APIRouter()


def get_db() -> Generator[Database, None, None]:
    db = Database()
    try:
        yield db
    finally:
        if db.conn:
            db.conn.close()


class WorkspaceCreateRequest(BaseModel):
    workspace_name: str = Field(..., description="Workspace name")
    user_id: str = Field(default="default_user", description="Owning user identifier")


class WorkspaceFileRequest(BaseModel):
    file_name: str = Field(..., description="Filename to register in workspace")


class DocIdRequest(BaseModel):
    doc_id: str = Field(..., description="Document identifier to associate")


class DeleteDocIdsRequest(BaseModel):
    workspaceInfo: Dict[str, Union[str, int]]
    fileInfo: Dict[str, Union[str, int]]


@router.get("/")
async def get_all_workspaces(db: Database = Depends(get_db)):
    try:
        workspaces = db.get_all_workspaces()
        if workspaces is None:
            logger.error("Database error while retrieving workspaces")
            return JSONResponse(
                content={
                    "status": "error",
                    "error_type": "database_error",
                    "message": "Failed to retrieve workspaces",
                },
                status_code=500,
            )

        logger.info(f"Retrieved {len(workspaces)} workspaces")
        return JSONResponse(
            content={
                "status": "success",
                "message": f"Retrieved {len(workspaces)} workspaces",
                "data": workspaces,
            },
            status_code=200,
        )
    except Exception as exc:  # pragma: no cover - database failure
        logger.error(f"Error retrieving workspaces: {str(exc)}")
        return JSONResponse(
            content={
                "status": "error",
                "error_type": "server_error",
                "message": f"Failed to retrieve workspaces: {str(exc)}",
            },
            status_code=500,
        )


@router.get("/{workspace_name}")
async def get_workspace(
    workspace_name: str = Path(..., description="Workspace name"),
    db: Database = Depends(get_db),
):
    try:
        workspace = db.get_workspace_details(workspace_name)
        if workspace is None:
            logger.warning(f"Workspace not found: {workspace_name}")
            return JSONResponse(
                content={
                    "status": "error",
                    "error_type": "not_found",
                    "message": f"Workspace '{workspace_name}' not found",
                },
                status_code=404,
            )

        logger.info(f"Retrieved workspace: {workspace_name}")
        return JSONResponse(
            content={
                "status": "success",
                "message": "Retrieved workspace details",
                "data": workspace,
            },
            status_code=200,
        )
    except Exception as exc:
        logger.error(f"Error retrieving workspace {workspace_name}: {str(exc)}")
        return JSONResponse(
            content={
                "status": "error",
                "error_type": "server_error",
                "message": f"Failed to retrieve workspace: {str(exc)}",
            },
            status_code=500,
        )


@router.post("/")
async def create_workspace(
    payload: WorkspaceCreateRequest, db: Database = Depends(get_db)
):
    try:
        workspace_name = payload.workspace_name.strip()
        if not workspace_name:
            logger.warning("Missing workspace_name in request")
            return JSONResponse(
                content={
                    "status": "error",
                    "error_type": "missing_parameter",
                    "message": "Missing workspace_name parameter",
                },
                status_code=400,
            )

        existing = db.get_workspace_by_name(workspace_name)
        if existing:
            logger.info(f"Workspace already exists: {workspace_name}")
            workspace = db.get_workspace_details(workspace_name)
            return JSONResponse(
                content={
                    "status": "success",
                    "message": f"Workspace '{workspace_name}' already exists",
                    "data": workspace,
                    "already_exists": True,
                },
                status_code=200,
            )

        workspace_dir = os.path.join(cfg.UPLOAD_DIR, workspace_name)
        os.makedirs(workspace_dir, exist_ok=True)
        logger.info(f"Created workspace directory: {workspace_dir}")

        workspace_id = db.create_workspace(payload.user_id, workspace_name)
        if not workspace_id:
            logger.error(f"Failed to create workspace: {workspace_name}")
            return JSONResponse(
                content={
                    "status": "error",
                    "error_type": "database_error",
                    "message": "Failed to create workspace in database",
                },
                status_code=500,
            )

        logger.info(f"Created workspace: {workspace_name} (ID: {workspace_id})")
        workspace = db.get_workspace_details(workspace_name)

        return JSONResponse(
            content={
                "status": "success",
                "message": f"Created workspace '{workspace_name}'",
                "data": workspace,
                "already_exists": False,
            },
            status_code=201,
        )
    except Exception as exc:
        logger.error(f"Error creating workspace: {str(exc)}")
        return JSONResponse(
            content={
                "status": "error",
                "error_type": "server_error",
                "message": f"Failed to create workspace: {str(exc)}",
            },
            status_code=500,
        )


@router.get("/{workspace_name}/files")
async def get_workspace_files(
    workspace_name: str = Path(..., description="Workspace name"),
    db: Database = Depends(get_db),
):
    try:
        workspace = db.get_workspace_by_name(workspace_name)
        if not workspace:
            logger.warning(f"Workspace not found: {workspace_name}")
            return JSONResponse(
                content={
                    "status": "error",
                    "error_type": "not_found",
                    "message": f"Workspace '{workspace_name}' not found",
                },
                status_code=404,
            )

        files = db.get_workspace_files_detailed(workspace["id"])
        logger.info(
            f"Retrieved {len(files) if files else 0} files from workspace '{workspace_name}'"
        )
        return JSONResponse(
            content={
                "status": "success",
                "message": f"Retrieved {len(files) if files else 0} files",
                "data": {"workspace": workspace_name, "files": files or []},
            },
            status_code=200,
        )
    except Exception as exc:
        logger.error(
            f"Error retrieving files for workspace {workspace_name}: {str(exc)}"
        )
        return JSONResponse(
            content={
                "status": "error",
                "error_type": "server_error",
                "message": f"Failed to retrieve files: {str(exc)}",
            },
            status_code=500,
        )


@router.post("/{workspace_name}/files")
async def add_file_to_workspace_api(
    workspace_name: str,
    payload: WorkspaceFileRequest,
    db: Database = Depends(get_db),
):
    try:
        workspace = db.get_workspace_by_name(workspace_name)
        if not workspace:
            logger.warning(f"Workspace not found: {workspace_name}")
            return JSONResponse(
                content={
                    "status": "error",
                    "error_type": "not_found",
                    "message": f"Workspace '{workspace_name}' not found",
                },
                status_code=404,
            )

        workspace_id = workspace["id"]
        file_exists, existing_file_id = db.check_file_exists_in_workspace(
            workspace_id, payload.file_name
        )
        if file_exists:
            logger.info(f"File already exists in workspace: {payload.file_name}")
            return JSONResponse(
                content={
                    "status": "success",
                    "message": "File already exists in workspace",
                    "data": {
                        "file_name": payload.file_name,
                        "already_exists": True,
                        "file_id": existing_file_id,
                    },
                },
                status_code=200,
            )

        file_path = os.path.join(workspace_name, payload.file_name)
        file_id = db.add_file_to_workspace(workspace_id, payload.file_name, file_path)
        if not file_id:
            logger.error(f"Failed to add file to database: {payload.file_name}")
            return JSONResponse(
                content={
                    "status": "error",
                    "error_type": "database_error",
                    "message": "Failed to add file to database",
                },
                status_code=500,
            )

        logger.info(
            f"Added file to workspace database: {payload.file_name} (ID: {file_id})"
        )
        return JSONResponse(
            content={
                "status": "success",
                "message": f"Added file to workspace '{workspace_name}'",
                "data": {
                    "file_id": file_id,
                    "file_name": payload.file_name,
                    "workspace_name": workspace_name,
                },
            },
            status_code=201,
        )
    except Exception as exc:
        logger.exception(
            f"Error adding file to workspace {workspace_name}: {str(exc)}"
        )
        return JSONResponse(
            content={
                "status": "error",
                "error_type": "server_error",
                "message": str(exc),
            },
            status_code=500,
        )


@router.delete("/{workspace_name}")
async def delete_workspace(
    workspace_name: str = Path(..., description="Workspace name"),
    db: Database = Depends(get_db),
):
    try:
        if not workspace_name:
            logger.warning("Missing workspace_name in request")
            return JSONResponse(
                content={
                    "status": "error",
                    "error_type": "missing_parameter",
                    "message": "Missing workspace_name parameter",
                },
                status_code=400,
            )

        workspace_details = db.get_workspace_by_name(workspace_name)
        if not workspace_details:
            logger.warning(f"Workspace not found: {workspace_name}")
            return JSONResponse(
                content={
                    "status": "error",
                    "error_type": "not_found",
                    "message": f"Workspace '{workspace_name}' not found",
                },
                status_code=404,
            )

        workspace_info = {
            "id": workspace_details["id"],
            "workspace_name": workspace_details["workspace_name"],
        }
        delete_success = delete_workspace_api(workspace_info)
        if not delete_success:
            logger.error(f"Failed to delete workspace: {workspace_name}")
            return JSONResponse(
                content={"status": "error", "message": "Failed to delete workspace"},
                status_code=500,
            )

        logger.info(f"Deleted workspace: {workspace_name}")
        return JSONResponse(
            content={
                "status": "success",
                "message": f"Deleted workspace '{workspace_name}'",
            },
            status_code=200,
        )
    except Exception as exc:
        logger.error(f"Error deleting workspace {workspace_name}: {str(exc)}")
        return JSONResponse(
            content={
                "status": "error",
                "error_type": "server_error",
                "message": f"Failed to delete workspace: {str(exc)}",
            },
            status_code=500,
        )


@router.delete("/{workspace_name}/{file_id}")
async def delete_workspace_file(
    workspace_name: str,
    file_id: int,
    db: Database = Depends(get_db),
):
    try:
        workspace = db.get_workspace_by_name(workspace_name)
        if not workspace:
            logger.warning(f"Workspace not found: {workspace_name}")
            return JSONResponse(
                content={
                    "status": "error",
                    "error_type": "not_found",
                    "message": f"Workspace '{workspace_name}' not found",
                },
                status_code=404,
            )

        file_info = db.get_file_details(file_id)
        if not file_info:
            logger.warning(
                f"File not found: ID {file_id} in workspace {workspace_name}"
            )
            return JSONResponse(
                content={
                    "status": "error",
                    "error_type": "not_found",
                    "message": f"File ID {file_id} not found in workspace",
                },
                status_code=404,
            )

        delete_success = db.delete_workspace_file(file_id)
        if not delete_success:
            logger.error(f"Database error deleting file ID {file_id}")
            return JSONResponse(
                content={
                    "status": "error",
                    "error_type": "database_error",
                    "message": "Failed to delete file from database",
                },
                status_code=500,
            )

        file_path = os.path.join(cfg.UPLOAD_DIR, workspace_name, file_info["file_name"])
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Deleted file: {file_path}")

        return JSONResponse(
            content={
                "status": "success",
                "message": f"Deleted file from workspace '{workspace_name}'",
                "data": {
                    "file_id": file_id,
                    "file_name": file_info["file_name"],
                },
            },
            status_code=200,
        )
    except Exception as exc:
        logger.error(
            f"Error deleting file {file_id} from workspace {workspace_name}: {str(exc)}"
        )
        return JSONResponse(
            content={
                "status": "error",
                "error_type": "server_error",
                "message": f"Failed to delete file: {str(exc)}",
            },
            status_code=500,
        )


@router.post("/{workspace_name}/{file_id}/doc_ids")
async def add_doc_id_to_workspace_file(
    workspace_name: str,
    file_id: int,
    payload: DocIdRequest,
    db: Database = Depends(get_db),
):
    try:
        workspace = db.get_workspace_by_name(workspace_name)
        if not workspace:
            return JSONResponse(
                content={
                    "status": "error",
                    "message": f"Workspace '{workspace_name}' not found.",
                },
                status_code=404,
            )

        file_info = db.get_file_details(file_id)
        if not file_info:
            return JSONResponse(
                content={
                    "status": "error",
                    "message": f"File ID {file_id} not found in workspace '{workspace_name}'.",
                },
                status_code=404,
            )

        row_id = db.add_workspace_file_docID(workspace["id"], file_id, payload.doc_id)
        return JSONResponse(
            content={
                "status": "success",
                "message": f"Added doc_id to file {file_id}.",
                "data": {"row_id": row_id, "doc_id": payload.doc_id},
            },
            status_code=201,
        )
    except Exception as exc:
        return JSONResponse(
            content={"status": "error", "message": str(exc)},
            status_code=500,
        )


@router.get("/{workspace_name}/{file_id}/doc_ids")
async def get_doc_ids_for_workspace_file(
    workspace_name: str,
    file_id: int,
    db: Database = Depends(get_db),
):
    try:
        workspace = db.get_workspace_by_name(workspace_name)
        if not workspace:
            return JSONResponse(
                content={
                    "status": "error",
                    "message": f"Workspace '{workspace_name}' not found.",
                },
                status_code=404,
            )

        file_info = db.get_file_details(file_id)
        if not file_info:
            return JSONResponse(
                content={
                    "status": "error",
                    "message": f"File ID {file_id} not found in workspace '{workspace_name}'.",
                },
                status_code=404,
            )

        doc_ids = db.get_workspace_file_docIDs(
            workspace_id=workspace["id"], file_id=file_id
        )
        return JSONResponse(
            content={"status": "success", "data": doc_ids},
            status_code=200,
        )
    except Exception as exc:
        return JSONResponse(
            content={"status": "error", "message": str(exc)},
            status_code=500,
        )


@router.delete("/delete/doc_ids")
async def delete_files_from_workspace(
    payload: DeleteDocIdsRequest, db: Database = Depends(get_db)
):
    try:
        if not payload.workspaceInfo or not payload.fileInfo:
            return JSONResponse(
                content={
                    "status": "error",
                    "message": "Missing workspaceInfo or fileInfo in JSON body.",
                },
                status_code=400,
            )

        workspace_info = {
            "id": payload.workspaceInfo.get("id"),
            "workspace_name": payload.workspaceInfo.get("workspace_name"),
        }
        file_info = {
            "id": payload.fileInfo.get("id"),
            "file_name": payload.fileInfo.get("file_name"),
        }

        logger.info(f"Workspace Info: {workspace_info}")
        logger.info(f"File Info: {file_info}")

        doc_ids = db.get_workspace_file_docIDs(
            workspace_id=workspace_info["id"], file_id=file_info["id"]
        )
        if not doc_ids:
            return JSONResponse(
                content={
                    "status": "error",
                    "message": "No document IDs found for this file.",
                },
                status_code=404,
            )

        delete_success = delete_file_api(workspace_info, file_info)
        if not delete_success:
            return JSONResponse(
                content={
                    "status": "error",
                    "message": "Failed to delete file from database.",
                },
                status_code=500,
            )

        return JSONResponse(
            content={
                "status": "success",
                "message": (
                    f"Deleted file {file_info['file_name']} from workspace "
                    f"'{workspace_info['workspace_name']}'."
                ),
            },
            status_code=200,
        )
    except Exception as exc:
        logger.error(f"Error in delete_files_from_workspace: {exc}")
        return JSONResponse(
            content={"status": "error", "message": str(exc)},
            status_code=500,
        )