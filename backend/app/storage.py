import hashlib
from pathlib import Path

from fastapi import UploadFile

from app.errors import ApiError

CHUNK_SIZE = 1024 * 1024


async def save_upload(upload: UploadFile, target: Path, max_bytes: int) -> tuple[int, str]:
    """Stream an upload to disk, returning its size and SHA-256.

    Never reads the whole body: these are media files, and a five-gigabyte
    upload buffered in memory takes the container with it.
    """
    digest = hashlib.sha256()
    written = 0

    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as sink:
        while chunk := await upload.read(CHUNK_SIZE):
            written += len(chunk)
            if written > max_bytes:
                sink.close()
                target.unlink(missing_ok=True)
                raise ApiError(
                    413,
                    "upload_too_large",
                    f"The file exceeds the {max_bytes} byte limit.",
                    max_bytes=max_bytes,
                )
            digest.update(chunk)
            sink.write(chunk)

    if written == 0:
        target.unlink(missing_ok=True)
        raise ApiError(400, "empty_upload", "The uploaded file is empty.")

    return written, digest.hexdigest()
