from datetime import datetime
from functools import lru_cache
from pathlib import Path
from warnings import warn
from zoneinfo import ZoneInfo

import ffmpeg
import httpx
from pydantic import BaseModel

from .config import config
from .models import Image

WEBCAMS_URL = "https://ntvplus.ca/webcams?_data=routes%2F%24"

# The site no longer exposes the slugs used by existing archives and config. Keep
# mapping its feed titles back to those stable identifiers.
CAMERA_SLUGS = {
    "St. John's - Harbour": "stjohns-sky",
    "St. John's - Admiral's Green": "admiralsgreen",
    "St. John's - Downtown": "downtown",
    "St. John's - George Street": "georgestreet",
    "St. John's - Quidi Vidi Lake": "quidividilake",
    "Corner Brook": "cornerbrook",
    "Grand Falls-Windsor": "gfw-highstreet",
    "Port de Grave": "portdegrave",
    "Portugal Cove-St. Philips": "stphilips-bellisland",
    "St. John's - Logy Bay Road": "logybayroad",
}

session = httpx.Client(
    headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
)


class Camera(BaseModel):
    name: str
    slug: str
    feed_url: str

    def __hash__(self) -> int:
        return hash(self.slug)


@lru_cache
def list_cameras() -> list[Camera]:
    response = session.get(WEBCAMS_URL)
    response.raise_for_status()

    entries = response.json()["serverLoadedFeeds"][0]["feed"]["entry"]
    cameras = []

    for entry in entries:
        title = entry["title"]
        slug = CAMERA_SLUGS.get(title)
        if slug is None:
            warn(
                f"Webcam feed {title!r} has no legacy slug and will be skipped",
                stacklevel=2,
            )
            continue

        cameras.append(
            Camera(
                name=title,
                slug=slug,
                feed_url=entry["link"]["href"],
            )
        )

    return cameras


@lru_cache
def get_stream_hls_url(feed_url: str) -> str:
    response = session.get(feed_url)
    response.raise_for_status()
    return response.json()["entry"][0]["content"]["src"]


def save_stream_frame(hls_url: str, output_path: Path) -> None:
    try:
        ffmpeg.input(hls_url).output(str(output_path), vframes=1).run(
            capture_stdout=True, capture_stderr=True
        )
    except ffmpeg.Error as e:
        raise RuntimeError(f"ffmpeg error: {e.stderr.decode()}") from e


def save_camera_image(camera: Camera) -> None:
    print("Saving image for", camera.name)

    stream_hls_url = get_stream_hls_url(camera.feed_url)

    timestamp = datetime.now(tz=ZoneInfo("America/St_Johns"))
    filename = timestamp.strftime(
        config.output_file_name_format + "." + config.output_file_format
    )
    relative_path = (
        Path(camera.slug)
        / str(timestamp.year)
        / f"{timestamp.month:02d}"
        / f"{timestamp.day:02d}"
        / filename
    )
    output_path = config.output_path / relative_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    save_stream_frame(stream_hls_url, output_path)
    Image.add(camera.slug, timestamp, relative_path)

    print("Saved image for", camera.name)


def save_all_camera_images() -> None:
    for camera in list_cameras():
        if (
            config.target_cameras is not None
            and camera.slug not in config.target_cameras
        ) or camera.slug in config.excluded_cameras:
            continue

        try:
            save_camera_image(camera)
        # Keep processing the remaining cameras if one feed, filesystem write,
        # or database operation fails unexpectedly.
        except Exception as e:  # noqa: BLE001
            print(f"Error saving image for {camera.name}: {e}")
