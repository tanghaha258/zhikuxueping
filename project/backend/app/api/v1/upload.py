import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.deps import get_current_media_user, get_current_user, require_roles
from app.core.exceptions import AppException
from app.core.response import success_response
from app.models.user import User

router = APIRouter(prefix="/upload", tags=["文件上传"])

ALLOWED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp",
    ".pdf", ".doc", ".docx", ".xlsx", ".pptx",
    ".zip", ".rar",
}


def _protected_url(relative_path: str) -> str:
    return f"/api/v1/upload/files/{relative_path.replace(os.sep, '/')}"


def _resolve_upload_path(file_path: str) -> Path:
    upload_root = Path(settings.UPLOAD_DIR).resolve()
    resolved_path = (upload_root / file_path).resolve()
    if upload_root not in resolved_path.parents or not resolved_path.is_file():
        raise AppException(code=40401, message="file not found", status_code=404)
    return resolved_path


@router.post("", summary="上传文件")
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if not ext or ext not in ALLOWED_EXTENSIONS:
        raise AppException(code=40004, message="不支持的文件类型")

    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE:
        raise AppException(code=40005, message="文件大小超过10MB限制")

    unique_name = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, unique_name)

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    with open(file_path, "wb") as f:
        f.write(content)

    return success_response(data={
        "url": _protected_url(unique_name),
        "filename": file.filename,
        "size": len(content),
    })


@router.post("/image", summary="上传图片（Tiptap 编辑器用）")
async def upload_image(
    file: UploadFile = File(...),
    current_user: User = Depends(require_roles(["teacher", "school_admin"])),
):
    if file.content_type not in settings.ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {file.content_type}")
    content = await file.read()
    if len(content) > settings.MAX_IMAGE_SIZE:
        raise HTTPException(status_code=400, detail="文件大小超过 5MB 限制")
    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "jpg"
    filename = f"{uuid.uuid4().hex}.{ext}"
    subdir = os.path.join(settings.UPLOAD_DIR, "images", current_user.id)
    os.makedirs(subdir, exist_ok=True)
    filepath = os.path.join(subdir, filename)
    with open(filepath, "wb") as f:
        f.write(content)
    return {"code": 0, "data": {"url": _protected_url(f"images/{current_user.id}/{filename}")}}


@router.get("/files/{file_path:path}")
def download_file(
    file_path: str,
    current_user: User = Depends(get_current_media_user),
):
    return FileResponse(_resolve_upload_path(file_path))
