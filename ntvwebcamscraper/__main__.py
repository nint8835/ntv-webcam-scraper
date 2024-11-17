import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import typer
from scheduler import Scheduler

from .config import config
from .timelapse import create_timelapse
from .webcams import save_all_camera_images

app = typer.Typer()


@app.command()
def scrape():
    """Scrape the webcam images once."""
    save_all_camera_images()


@app.command()
def run():
    """Begin scraping the webcam images at the specified interval."""
    schedule = Scheduler()
    schedule.cyclic(config.interval, save_all_camera_images)

    while True:
        schedule.exec_jobs()
        time.sleep(1)


@app.command()
def timelapse(
    camera: str,
    from_date: datetime,
    to_date: datetime,
):
    """Create a timelapse from the saved images."""

    from_date = from_date.replace(tzinfo=ZoneInfo("America/St_Johns"))
    to_date = to_date.replace(tzinfo=ZoneInfo("America/St_Johns"))

    if camera != "all":
        create_timelapse(camera, from_date, to_date, Path("timelapses"))

    for subdir in config.output_path.iterdir():
        if not subdir.is_dir():
            continue

        create_timelapse(subdir.name, from_date, to_date, Path("timelapses"))


app()
