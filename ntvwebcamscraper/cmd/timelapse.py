from datetime import datetime
from pathlib import Path
from typing import Annotated, cast
from zoneinfo import ZoneInfo

import typer
from pydantic import BaseModel

from ntvwebcamscraper.timelapse import (
    FrameSelector,
    all_frames,
    create_timelapse,
    daily_frames,
)
from ntvwebcamscraper.webcams import list_cameras

from .utils import async_command

app = typer.Typer()


async def create_timelapses(
    camera: str,
    from_date: datetime,
    to_date: datetime,
    framerate: int,
    include_timestamp: bool,
    frame_selector: FrameSelector,
) -> None:
    from_date = from_date.replace(tzinfo=ZoneInfo("America/St_Johns"))
    to_date = to_date.replace(tzinfo=ZoneInfo("America/St_Johns"))

    if camera != "all":
        await create_timelapse(
            camera=camera,
            from_date=from_date,
            to_date=to_date,
            output_path=Path("timelapses"),
            framerate=framerate,
            include_timestamp=include_timestamp,
            frame_selector=frame_selector,
        )
        return

    for available_camera in await list_cameras():
        await create_timelapse(
            camera=available_camera.slug,
            from_date=from_date,
            to_date=to_date,
            output_path=Path("timelapses"),
            framerate=framerate,
            include_timestamp=include_timestamp,
            frame_selector=frame_selector,
        )


class TimelapseOptions(BaseModel):
    camera: str
    from_date: datetime
    to_date: datetime
    framerate: int
    include_timestamp: bool


@app.callback()
def timelapse_callback(
    ctx: typer.Context,
    camera: Annotated[str, typer.Option()],
    from_date: Annotated[datetime, typer.Option()],
    to_date: Annotated[datetime, typer.Option()],
    framerate: Annotated[int, typer.Option()] = 12,
    include_timestamp: Annotated[bool, typer.Option()] = False,
):
    ctx.obj = TimelapseOptions(
        camera=camera,
        from_date=from_date,
        to_date=to_date,
        framerate=framerate,
        include_timestamp=include_timestamp,
    )


@app.command()
@async_command
async def daily(
    ctx: typer.Context,
    hour: int,
    frames: int = 1,
) -> None:
    """Create a timelapse from a specified number of frames from a given hour each day."""

    options = cast(TimelapseOptions, ctx.obj)

    await create_timelapses(
        frame_selector=daily_frames(hour=hour, frames=frames),
        **options.model_dump(),
    )


@app.command()
@async_command
async def all(
    ctx: typer.Context,
) -> None:
    """Create a timelapse from all saved images."""

    options = cast(TimelapseOptions, ctx.obj)

    await create_timelapses(
        frame_selector=all_frames,
        **options.model_dump(),
    )


__all__ = ["app"]
