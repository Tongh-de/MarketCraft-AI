import hashlib
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

from app.core.config import get_settings
from app.domain.creation import UploadedProductImage


class UploadValidationError(Exception):
    pass


ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def _matches_image_signature(content_type: str, content: bytes) -> bool:
    if content_type == "image/png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/jpeg":
        return content.startswith(b"\xff\xd8\xff")
    if content_type == "image/webp":
        return len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP"
    return False


class ImageUploadService:
    def __init__(self, upload_dir: str | Path, max_upload_bytes: int) -> None:
        self.upload_dir = Path(upload_dir).resolve()
        self.max_upload_bytes = max_upload_bytes
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def save(self, filename: str, content_type: str, content: bytes) -> UploadedProductImage:
        if content_type not in ALLOWED_IMAGE_TYPES:
            raise UploadValidationError("only PNG, JPEG and WebP product images are supported")
        if not content:
            raise UploadValidationError("uploaded product image is empty")
        if len(content) > self.max_upload_bytes:
            raise UploadValidationError(
                f"uploaded product image exceeds {self.max_upload_bytes} bytes"
            )
        if not _matches_image_signature(content_type, content):
            raise UploadValidationError("file content does not match the declared image type")

        upload_id = uuid4()
        extension = ALLOWED_IMAGE_TYPES[content_type]
        stored_name = f"{upload_id}{extension}"
        destination = self.upload_dir / stored_name
        destination.write_bytes(content)
        return UploadedProductImage(
            upload_id=upload_id,
            original_filename=Path(filename).name or f"product{extension}",
            content_type=content_type,
            size_bytes=len(content),
            checksum_sha256=hashlib.sha256(content).hexdigest(),
            url=f"/uploads/{stored_name}",
        )


@lru_cache
def get_image_upload_service() -> ImageUploadService:
    settings = get_settings()
    return ImageUploadService(settings.upload_dir, settings.max_upload_bytes)
