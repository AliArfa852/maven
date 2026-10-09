"""Save a built file (src/file_builder.py) as the owner's upload.

Generated files go through the same upload store as files people attach, so
they get its type checks, size limit and owner-only download route
(/api/upload/{id}). Shared by the HTTP route and the agent tool.
"""
from __future__ import annotations

import io

from starlette.datastructures import UploadFile

from src.file_builder import BuiltFile, build_file, safe_filename
from src.tool_utils import get_upload_handler


class FileStoreUnavailable(RuntimeError):
    pass


def create_owned_file(fmt: str, spec: dict, filename: str, owner: str | None,
                      client: str = "file-builder") -> dict:
    """Build and store a file for ``owner``. Raises FileSpecError on bad specs."""
    built: BuiltFile = build_file(fmt, spec)
    handler = get_upload_handler()
    if handler is None:
        raise FileStoreUnavailable("file storage is not ready")
    name = safe_filename(filename or spec.get("title") or "document", built.extension)
    saved = handler.save_upload(UploadFile(file=io.BytesIO(built.data), filename=name),
                                client_ip=client, owner=owner)
    return {
        "id": saved["id"],
        "name": saved.get("name") or name,
        "mime": built.mime,
        "size": saved.get("size", len(built.data)),
        "url": f"/api/upload/{saved['id']}",
    }
