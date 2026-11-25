import typer
import uvicorn

from ntvwebcamscraper.config import config
from ntvwebcamscraper.database import upgrade_database
from ntvwebcamscraper.web import app as web_app
from ntvwebcamscraper.webcams import save_all_camera_images

from .migrate import migrate as _migrate
from .timelapse import app as timelapse_app

app = typer.Typer()
app.add_typer(timelapse_app, name="timelapse")


@app.callback()
def on_startup(ctx: typer.Context) -> None:
    if config.init_on_startup and ctx.invoked_subcommand != "run":
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
    """Serve the web app and scrape webcam images at the configured interval."""
    uvicorn.run(web_app, host="127.0.0.1", port=8000, workers=1, lifespan="on")


@app.command()
def upgrade() -> None:
    """Perform database migrations."""
    upgrade_database()


__all__ = ["app"]
