"""Create office files from a structured spec (plan v2 §5.1, R12).

POST /api/files/create {"format": "xlsx|docx|pptx|pdf|csv", "filename": "...",
"spec": {...}} builds the file (src/file_builder.py) and stores it as the
caller's own upload; the response carries its download URL.
"""
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.auth_helpers import effective_user
from src.file_builder import FORMATS, FileSpecError
from src.file_store import FileStoreUnavailable, create_owned_file


class CreateFileRequest(BaseModel):
    format: str = Field(..., description="xlsx, docx, pptx, pdf or csv")
    filename: str = Field(default="", max_length=120)
    spec: Dict[str, Any]


def setup_file_routes() -> APIRouter:
    router = APIRouter(prefix="/api/files", tags=["files"])

    @router.get("/formats")
    def formats():
        return {"formats": sorted(FORMATS)}

    @router.post("/create")
    def create_file(body: CreateFileRequest, request: Request):
        owner = effective_user(request)
        try:
            return create_owned_file(body.format, body.spec, body.filename, owner,
                                     client=(request.client.host if request.client else "file-builder"))
        except FileSpecError as e:
            raise HTTPException(400, str(e))
        except FileStoreUnavailable as e:
            raise HTTPException(503, str(e))

    return router
