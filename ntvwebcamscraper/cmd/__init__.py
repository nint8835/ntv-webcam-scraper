import time

import alembic.config
import typer
from scheduler import Scheduler

from ntvwebcamscraper.ai_analysis import test_analysis
from ntvwebcamscraper.config import config
from ntvwebcamscraper.database import merge_pending_migration
from ntvwebcamscraper.webcams import save_all_camera_images

from .migrate import migrate as _migrate
from .timelapse import app as timelapse_app

app = typer.Typer()
app.add_typer(timelapse_app, name="timelapse")


@app.callback()
def on_startup() -> None:
    if config.init_on_startup:
        upgrade()


@app.command()
def migrate():
    """Migrate images from flat directory structure to date-partitioned structure."""
    _migrate()


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
def upgrade() -> None:
    """Perform database migrations."""
    alembic.config.main(argv=["--raiseerr", "upgrade", "head"])

    merge_pending_migration()


@app.command()
def ai_test() -> None:
    """Test AI analysis."""

    test_analysis()


__all__ = ["app"]
