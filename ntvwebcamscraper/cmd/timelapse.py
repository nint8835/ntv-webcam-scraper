from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import typer

from ntvwebcamscraper.config import config
from ntvwebcamscraper.timelapse import (
    FrameSelector,
    all_frames,
    create_timelapse,
    daily_frames,
)

app = typer.Typer()


def create_timelapses(
    camera: str,
    from_date: datetime,
    to_date: datetime,
    framerate: int,
    include_timestamp: bool,
    frame_selector: FrameSelector,
):
    from_date = from_date.replace(tzinfo=ZoneInfo("America/St_Johns"))
    to_date = to_date.replace(tzinfo=ZoneInfo("America/St_Johns"))

    if camera != "all":
        create_timelapse(
            camera=camera,
            from_date=from_date,
            to_date=to_date,
            output_path=Path("timelapses"),
            framerate=framerate,
            include_timestamp=include_timestamp,
            frame_selector=frame_selector,
        )
        return

    for subdir in config.output_path.iterdir():
        if not subdir.is_dir():
            continue

        create_timelapse(
            camera=subdir.name,
            from_date=from_date,
            to_date=to_date,
            output_path=Path("timelapses"),
            framerate=framerate,
            include_timestamp=include_timestamp,
            frame_selector=frame_selector,
        )


@app.command()
def daily(
    camera: str,
    from_date: datetime,
    to_date: datetime,
    hour: int,
    frames: int = 1,
    framerate: int = 12,
    include_timestamp: bool = False,
):
    """Create a timelapse from a specified number of frames from a given hour each day."""

    create_timelapses(
        camera=camera,
        from_date=from_date,
        to_date=to_date,
        framerate=framerate,
        include_timestamp=include_timestamp,
        frame_selector=daily_frames(hour=hour, frames=frames),
    )


@app.command()
def all(
    camera: str,
    from_date: datetime,
    to_date: datetime,
    framerate: int = 12,
    include_timestamp: bool = False,
):
    """Create a timelapse from all saved images."""

    create_timelapses(
        camera=camera,
        from_date=from_date,
        to_date=to_date,
        framerate=framerate,
        include_timestamp=include_timestamp,
        frame_selector=all_frames,
    )


__all__ = ["app"]
