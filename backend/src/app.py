import json
import os
import sys
import warnings
from contextlib import asynccontextmanager
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

# Suppress cryptography deprecation warnings
warnings.filterwarnings(
    "ignore",
    message=".*ARC4.*",
    category=DeprecationWarning,
    module=".*cryptography.*"
)

load_dotenv()

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import config as cfg  # noqa: E402
from logging_Setup import get_logger  # noqa: E402

from flaskAPI.auth import router as auth_router  # noqa: E402
from flaskAPI.chatAPI import router as chat_router  # noqa: E402
from flaskAPI.fileAccess import router as file_access_router  # noqa: E402
from flaskAPI.fileManagerAPI import router as file_manager_router  # noqa: E402
from flaskAPI.fileProcessingAPI import router as file_processing_router  # noqa: E402
from flaskAPI.workspaceManagerAPI import router as workspace_router  # noqa: E402

logger = get_logger(__name__)

PASSWORD = os.environ["ADMIN_PASSWORD"]
EXCLUDE_PATHS = ["/health", "/auth/validate", "/fileAccess/"]
APP_ENV = os.environ.get("APP_ENV", "development")
logger.info(f"Starting FastAPI backend in '{APP_ENV}' mode")


def _parse_frontend_origins(origins: Optional[str]) -> List[str]:
    if origins is None:
        return ["http://localhost"]

    if isinstance(origins, list):
        return origins

    origins = origins.strip()
    if origins.startswith("["):
        try:
            parsed = json.loads(origins)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            logger.warning("Failed to JSON decode FRONTEND_ORIGINS, falling back to CSV parsing")

    return [origin.strip() for origin in origins.split(",") if origin.strip()]


configured_origins = _parse_frontend_origins(cfg.FRONTEND_ORIGINS)
logger.info(f"Allowed origins: {configured_origins}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Application startup")
    yield
    # Shutdown
    logger.info("Application shutdown - cleaning up resources...")


app = FastAPI(title="Multi Model RAG Agent API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=configured_origins or ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Secret-Key", "Authorization", "secret_key"],
    expose_headers=["Content-Type", "X-Secret-Key", "Authorization"],
)


def _resolve_allowed_origin(origin: Optional[str]) -> Optional[str]:
    if not configured_origins:
        return origin

    if origin is None:
        return configured_origins[0]

    if origin in configured_origins:
        return origin

    return configured_origins[0]


@app.middleware("http")
async def global_basic_auth(request: Request, call_next):
    origin = request.headers.get("Origin")
    allowed_origin = _resolve_allowed_origin(origin)

    if request.method == "OPTIONS":
        response = Response(status_code=200)
        if allowed_origin:
            response.headers["Access-Control-Allow-Origin"] = allowed_origin
        response.headers["Access-Control-Allow-Headers"] = (
            "Content-Type, X-Secret-Key, Authorization, secret_key"
        )
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        return response

    if any(request.url.path.startswith(path) for path in EXCLUDE_PATHS):
        response = await call_next(request)
        if allowed_origin:
            response.headers["Access-Control-Allow-Origin"] = allowed_origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        return response

    secret_key = request.headers.get("X-Secret-Key")
    if not secret_key:
        response = JSONResponse(
            content={"error": "Missing secret key header"},
            status_code=401,
        )
        if allowed_origin:
            response.headers["Access-Control-Allow-Origin"] = allowed_origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        return response

    if secret_key != PASSWORD:
        response = JSONResponse(
            content={"error": "Invalid secret key"},
            status_code=401,
        )
        if allowed_origin:
            response.headers["Access-Control-Allow-Origin"] = allowed_origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        return response

    response = await call_next(request)
    if allowed_origin:
        response.headers["Access-Control-Allow-Origin"] = allowed_origin
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        content={"error": "Internal server error", "details": str(exc)},
        status_code=500,
    )


app.include_router(file_manager_router, prefix="/files", tags=["files"])
app.include_router(file_processing_router, prefix="/process_file", tags=["processing"])
app.include_router(workspace_router, prefix="/workspaces", tags=["workspaces"])
app.include_router(chat_router, prefix="/chat", tags=["chat"])
app.include_router(file_access_router, prefix="/fileAccess", tags=["file access"])
app.include_router(auth_router, prefix="/auth", tags=["auth"])


class LogEntry(BaseModel):
    timestamp: str
    level: str
    message: str
    data: Optional[dict] = None
    user_id: Optional[str] = None


class LogRequest(BaseModel):
    logs: List[LogEntry] = Field(default_factory=list)


@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Service is running"}


@app.post("/logs")
async def store_logs(payload: LogRequest):
    frontend_log_file = os.path.join(cfg.LOGS_FILE, "frontend_application.log")
    os.makedirs(os.path.dirname(frontend_log_file), exist_ok=True)

    with open(frontend_log_file, "a", encoding="utf-8") as log_file:
        for log in payload.logs:
            log_file.write(f"{log.timestamp} [{log.level}] {log.user_id}: {log.message}\n")
            if log.data:
                log_file.write(f"  Data: {json.dumps(log.data)}\n")

    return {"success": True}


@app.get("/secureapi")
async def secure_api():
    return {"message": "This is a secure API endpoint."}

