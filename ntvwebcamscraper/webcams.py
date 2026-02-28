import json
import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

import ffmpeg
import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel

from .config import config
from .models import Image

WEBCAMS_PAGE = "https://ntvplus.ca/pages/webcams"
WEBCAM_URL_PREFIX = "https://ntvplus.ca/pages/webcam-"

session = httpx.Client(
    headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
)


class Camera(BaseModel):
    name: str
    slug: str

    def __hash__(self) -> int:
        return hash(self.slug)


@lru_cache
def list_cameras() -> list[Camera]:
    return [
        Camera(
            name="Admiral's Green",
            slug="admiralsgreen",
        ),
        Camera(name="Corner Brook", slug="cornerbrook"),
        Camera(name="Downtown", slug="downtown"),
        Camera(name="George Street", slug="georgestreet"),
        Camera(name="GFW High Street", slug="gfw-highstreet"),
        Camera(name="Logy Bay Road", slug="logybayroad"),
        Camera(name="Port de Grave", slug="portdegrave"),
        Camera(name="Quidi Vidi Lake", slug="quidividilake"),
        Camera(name="Quidi Vidi Village", slug="quidividivillage"),
        Camera(name="St. John's Sky", slug="stjohns-sky"),
        Camera(name="St. Philip's - Bell Island", slug="stphilips-bellisland"),
    ]

    cameras_page = session.get(WEBCAMS_PAGE)
    cameras_page.raise_for_status()

    soup = BeautifulSoup(cameras_page.text, "html.parser")

    cameras = []

    page_div = soup.find("div", class_="page")

    for camera_a in page_div.find_all("a"):
        title_h3 = camera_a.find("h3")

        cameras.append(
            Camera(
                name=title_h3.text,
                slug=camera_a["href"].split("/")[-1].removeprefix("webcam-"),
            )
        )

    return cameras


@lru_cache
def get_stream_iframe_url(camera: Camera) -> str:
    camera_page = session.get(WEBCAM_URL_PREFIX + camera.slug)
    camera_page.raise_for_status()

    soup = BeautifulSoup(camera_page.text, "html.parser")
    iframe = soup.find(
        lambda element: (
            element.name == "iframe" and "https://c.streamhoster.com" in element["src"]
        )
    )

    return iframe["src"]


@lru_cache
def get_stream_hls_url(iframe_url: str) -> str:
    stream_page = session.get(iframe_url)
    stream_page.raise_for_status()

    soup = BeautifulSoup(stream_page.text, "html.parser")
    hls_script = soup.find(
        lambda element: (element.name == "script" and "var shCfg" in element.text)
    )

    shcfg = json.loads(re.findall(r"var shCfg = (.*);\n", hls_script.text)[0])

    return shcfg["mediaUrlTemplate"]["hlsAdaptiveUrl"]["url"]


def save_stream_frame(hls_url: str, output_path: Path) -> None:
    try:
        ffmpeg.input(hls_url).output(str(output_path), vframes=1).run(
            capture_stdout=True, capture_stderr=True
        )
    except ffmpeg.Error as e:
        raise RuntimeError(f"ffmpeg error: {e.stderr.decode()}") from e


def save_camera_image(camera: Camera) -> None:
    print("Saving image for", camera.name)

    stream_frame_url = get_stream_iframe_url(camera)
    stream_hls_url = get_stream_hls_url(stream_frame_url)

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
        except Exception as e:
            print(f"Error saving image for {camera.name}: {e}")
