import hashlib
from datetime import UTC, datetime
from email.utils import format_datetime, parsedate_to_datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
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


def _strip_weak(tag: str) -> str:
    return tag.removeprefix("W/")


def _is_not_modified(
    etag: str,
    last_modified: datetime,
    if_none_match: str | None,
    if_modified_since: str | None,
) -> bool:
    """Evaluate GET preconditions per RFC 9110 section 13.2.2."""
    # If-None-Match takes precedence; If-Modified-Since is ignored when present.
    if if_none_match is not None:
        tags = [tag.strip() for tag in if_none_match.split(",")]
        return "*" in tags or _strip_weak(etag) in {_strip_weak(t) for t in tags}

    if if_modified_since is not None:
        try:
            since = parsedate_to_datetime(if_modified_since)
        except TypeError, ValueError:
            # An invalid date means the header must be ignored.
            return False
        if since.tzinfo is None:
            since = since.replace(tzinfo=UTC)
        # Last-Modified only has whole-second precision.
        return last_modified.replace(microsecond=0) <= since

    return False


@router.get(
    "/{image_id}",
    response_class=FileResponse,
    responses={
        200: {
            "description": "The image file",
            "content": {"image/*": {"schema": {"type": "string", "format": "binary"}}},
        },
        304: {"description": "The image has not changed since the cached copy"},
        404: {"model": ErrorResponse, "description": "Image not found"},
    },
)
async def get_image(
    image_id: int,
    db: DatabaseSession,
    if_none_match: Annotated[str | None, Header()] = None,
    if_modified_since: Annotated[str | None, Header()] = None,
) -> Response:
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
    etag_hash = hashlib.md5(etag_base.encode(), usedforsecurity=False).hexdigest()
    etag = f'"{etag_hash}"'
    headers = {
        "last-modified": format_datetime(captured_at.astimezone(UTC), usegmt=True),
        "etag": etag,
    }

    if _is_not_modified(etag, captured_at, if_none_match, if_modified_since):
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)

    return FileResponse(path, headers=headers)
