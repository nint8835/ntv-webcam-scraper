import time

import typer
from scheduler import Scheduler

from ntvwebcamscraper.config import config
from ntvwebcamscraper.database import db
from ntvwebcamscraper.webcams import save_all_camera_images

from .migrate import migrate as _migrate
from .timelapse import app as timelapse_app

app = typer.Typer()
app.add_typer(timelapse_app, name="timelapse")


@app.command()
def migrate():
    """Migrate images from flat directory structure to date-partitioned structure."""
    _migrate()


@app.command()
def scrape():
    """Scrape the webcam images once."""
    db.init_db()
    save_all_camera_images()


@app.command()
def run():
    """Begin scraping the webcam images at the specified interval."""
    db.init_db()

    schedule = Scheduler()
    schedule.cyclic(config.interval, save_all_camera_images)

    while True:
        schedule.exec_jobs()
        time.sleep(1)


__all__ = ["app"]
