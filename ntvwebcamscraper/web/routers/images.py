import hashlib
from datetime import UTC, datetime
from email.utils import format_datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from ntvwebcamscraper.config import config
from ntvwebcamscraper.models import Image
from ntvwebcamscraper.web.auth import AUTH_RESPONSES, ErrorResponse, require_auth
from ntvwebcamscraper.web.dependencies import DatabaseSession

# SQLite drops the UTC offset, so stored timestamps come back naive in the
# timezone the scraper captured them in.
CAPTURE_TIMEZONE = ZoneInfo("America/St_Johns")

router = APIRouter(
    prefix="/api/images",
    tags=["images"],
    dependencies=[Depends(require_auth)],
    responses=AUTH_RESPONSES,
)


def _aware(timestamp: datetime) -> datetime:
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=CAPTURE_TIMEZONE)
    return timestamp


@router.get(
    "/{image_id}",
    response_class=FileResponse,
    responses={
        200: {
            "description": "The image file",
            "content": {"image/*": {"schema": {"type": "string", "format": "binary"}}},
        },
        404: {"model": ErrorResponse, "description": "Image not found"},
    },
)
async def get_image(image_id: int, db: DatabaseSession) -> FileResponse:
    """Return the file for a captured image."""
    image = await db.get(Image, image_id)
    if image is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Image not found")

    root = config.output_path.resolve()
    path = (root / image.path).resolve()
    # Never serve anything outside the output directory, whatever the DB says.
    if not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Image not found")

    captured_at = _aware(image.captured_at)
    # Derive caching headers from the DB record rather than the file's mtime,
    # which may not reflect when the image was captured.
    etag_base = f"{image.id}-{captured_at.isoformat()}"
    etag = hashlib.md5(etag_base.encode(), usedforsecurity=False).hexdigest()
    return FileResponse(
        path,
        headers={
            "last-modified": format_datetime(captured_at.astimezone(UTC), usegmt=True),
            "etag": f'"{etag}"',
        },
    )
