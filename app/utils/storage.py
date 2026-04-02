from __future__ import annotations

import mimetypes
import os
import uuid

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename


def capsule_storage_dir(upload_folder: str, user_id: int, capsule_id: int) -> str:
    return os.path.join(upload_folder, str(user_id), str(capsule_id))


def allowed_category_and_extension(filename: str, allowed_image, allowed_audio, allowed_video, allowed_doc):
    """
    Determine category and extension based on the original filename extension.
    This is a first-line check; server-side open/download is still gated by unlock time.
    """
    ext = (filename.rsplit(".", 1)[-1] if "." in filename else "").lower()
    if ext in allowed_image:
        return "image", ext
    if ext in allowed_audio:
        return "audio", ext
    if ext in allowed_video:
        return "video", ext
    if ext in allowed_doc:
        return "document", ext
    return None, None


def validate_upload(file: FileStorage, app_config) -> tuple[str, str, str, int]:
    """
    Returns: (file_category, stored_extension, mime_type, size_bytes)
    Raises ValueError on invalid uploads.
    """
    if not file or not file.filename:
        raise ValueError("Missing file.")

    original_filename = file.filename
    file_category, ext = allowed_category_and_extension(
        original_filename,
        app_config["ALLOWED_IMAGE_EXTENSIONS"],
        app_config["ALLOWED_AUDIO_EXTENSIONS"],
        app_config["ALLOWED_VIDEO_EXTENSIONS"],
        app_config["ALLOWED_DOCUMENT_EXTENSIONS"],
    )
    if not file_category:
        raise ValueError("Unsupported file type.")

    # Basic server-side MIME type guess by extension (not authoritative)
    mime_type, _ = mimetypes.guess_type(original_filename)
    mime_type = mime_type or file.mimetype or "application/octet-stream"

    # Size (werkzeug also enforces MAX_CONTENT_LENGTH at request level)
    # Avoid reading full file; use stream length if available.
    file.stream.seek(0, os.SEEK_END)
    size_bytes = file.stream.tell()
    file.stream.seek(0)

    max_size = int(app_config["MAX_CONTENT_LENGTH"])
    if size_bytes > max_size:
        raise ValueError("File is too large.")

    return file_category, ext, mime_type, size_bytes


def make_stored_filename(extension: str) -> str:
    return f"{uuid.uuid4().hex}.{extension.lower()}"


def safe_original_filename(filename: str) -> str:
    # Store a sanitized original name for UI; actual path never uses it.
    return secure_filename(filename)[:200] or "file"

