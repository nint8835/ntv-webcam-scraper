from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import typer

from ntvwebcamscraper.config import config
from ntvwebcamscraper.timelapse import create_timelapse, daily_frames

app = typer.Typer()


@app.command()
def timelapse(
    camera: str,
    from_date: datetime,
    to_date: datetime,
    framerate: int = 12,
    include_timestamp: bool = False,
):
    """Create a timelapse from the saved images."""

    from_date = from_date.replace(tzinfo=ZoneInfo("America/St_Johns"))
    to_date = to_date.replace(tzinfo=ZoneInfo("America/St_Johns"))

    selector = daily_frames(hour=10, frames=3)

    if camera != "all":
        create_timelapse(
            camera=camera,
            from_date=from_date,
            to_date=to_date,
            output_path=Path("timelapses"),
            framerate=framerate,
            include_timestamp=include_timestamp,
            frame_selector=selector,
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
            frame_selector=selector,
        )


__all__ = ["app"]
