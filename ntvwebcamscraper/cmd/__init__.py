import time

import alembic.config
import typer
from scheduler import Scheduler

from ntvwebcamscraper.config import config
from ntvwebcamscraper.database import merge_pending_migration
from ntvwebcamscraper.webcams import save_all_camera_images

from .migrate import migrate as _migrate
from .timelapse import app as timelapse_app

app = typer.Typer()
app.add_typer(timelapse_app, name="timelapse")


@app.command()
def migrate():
    """Migrate images from flat directory structure to date-partitioned structure."""

    if config.init_on_startup:
        upgrade()

    _migrate()


@app.command()
def scrape():
    """Scrape the webcam images once."""

    if config.init_on_startup:
        upgrade()

    save_all_camera_images()


@app.command()
def run():
    """Begin scraping the webcam images at the specified interval."""

    if config.init_on_startup:
        upgrade()

    schedule = Scheduler()
    schedule.cyclic(config.interval, save_all_camera_images)

    while True:
        schedule.exec_jobs()
        time.sleep(1)


@app.command()
def upgrade() -> None:
    """Perform database migrations."""
    alembic.config.main(argv=["--raiseerr", "upgrade", "head"])

    merge_pending_migration()


__all__ = ["app"]
