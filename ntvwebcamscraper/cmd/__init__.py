import typer
import uvicorn

from ntvwebcamscraper.config import config
from ntvwebcamscraper.database import upgrade_database
from ntvwebcamscraper.web import app as web_app
from ntvwebcamscraper.webcams import save_all_camera_images

from .migrate import migrate as _migrate
from .timelapse import app as timelapse_app
from .utils import async_command

app = typer.Typer()
app.add_typer(timelapse_app, name="timelapse")


@app.callback()
def on_startup(ctx: typer.Context) -> None:
    if config.init_on_startup and ctx.invoked_subcommand not in {"run", "upgrade"}:
        upgrade()


@app.command()
@async_command
async def migrate() -> None:
    """Migrate images from flat directory structure to date-partitioned structure."""
    await _migrate()


@app.command()
@async_command
async def scrape() -> None:
    """Scrape the webcam images once."""
    await save_all_camera_images()


@app.command()
def run():
    """Serve the web app and scrape webcam images at the configured interval."""
    uvicorn.run(web_app, host="127.0.0.1", port=8000, workers=1, lifespan="on")


@app.command()
@async_command
async def upgrade() -> None:
    """Perform database migrations."""
    await upgrade_database()


__all__ = ["app"]
