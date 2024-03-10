import json
import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import ffmpeg
import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel

from .config import config

WEBCAMS_PAGE = "https://ntvplus.ca/webcams/"
WEBCAM_URL_PREFIX = "https://ntvplus.ca/"

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
    cameras_page = session.get(WEBCAMS_PAGE)
    cameras_page.raise_for_status()

    soup = BeautifulSoup(cameras_page.text, "html.parser")

    cameras = []

    for camera_h3 in soup.find_all("h3", class_="boosted-elements-blog-title"):
        camera_a = camera_h3.find("a")

        cameras.append(Camera(name=camera_a.text, slug=camera_a["href"].split("/")[-2]))

    return cameras


@lru_cache
def get_stream_iframe_url(camera: Camera) -> str:
    camera_page = session.get(WEBCAM_URL_PREFIX + camera.slug + "/")
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
    ffmpeg.input(hls_url).output(str(output_path), vframes=1).run()


def save_camera_image(camera: Camera) -> None:
    stream_frame_url = get_stream_iframe_url(camera)
    stream_hls_url = get_stream_hls_url(stream_frame_url)

    output_path = (
        config.output_path
        / camera.slug
        / (datetime.now().replace(microsecond=0).isoformat() + ".png")
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    save_stream_frame(stream_hls_url, output_path)
