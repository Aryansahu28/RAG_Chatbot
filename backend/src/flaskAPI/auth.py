import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

PASSWORD = os.environ["ADMIN_PASSWORD"]

router = APIRouter()


class ValidateRequest(BaseModel):
    secret_key: str = Field(..., description="Shared admin secret")


@router.post("/validate")
async def validate_password(payload: ValidateRequest):
    if payload.secret_key == PASSWORD:
        return JSONResponse(
            content={"status": "success", "message": "Authentication successful"},
            status_code=200,
        )
    return JSONResponse(
        content={"status": "error", "message": "Invalid password"},
        status_code=401,
    )