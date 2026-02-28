import os
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import typer

from ntvwebcamscraper.config import config
from ntvwebcamscraper.database import db

NL_TZ = ZoneInfo("America/St_Johns")


def _flat_images() -> Iterator[tuple[str, os.DirEntry]]:
    with os.scandir(config.output_path) as cameras:
        for camera_entry in cameras:
            if not camera_entry.is_dir(follow_symlinks=False):
                continue
            with os.scandir(camera_entry.path) as images:
                for entry in images:
                    if entry.is_file(follow_symlinks=False) and entry.name.endswith(
                        ".jpg"
                    ):
                        yield camera_entry.name, entry


def migrate():
    """Migrate images from flat directory structure to date-partitioned structure."""
    db.init_db()

    with typer.progressbar(_flat_images(), label="Migrating images") as progress:
        for camera_name, entry in progress:
            try:
                timestamp = datetime.strptime(
                    entry.name,
                    config.output_file_name_format + "." + config.output_file_format,
                ).replace(tzinfo=NL_TZ)
            except ValueError:
                continue

            new_relative_path = (
                Path(camera_name)
                / str(timestamp.year)
                / f"{timestamp.month:02d}"
                / f"{timestamp.day:02d}"
                / entry.name
            )
            new_path = config.output_path / new_relative_path
            new_path.parent.mkdir(parents=True, exist_ok=True)
            Path(entry.path).rename(new_path)
            db.add_image(camera_name, timestamp, new_relative_path)


__all__ = ["migrate"]
