import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import ffmpeg

from .config import config


def list_camera_timestamps(
    camera: str, earliest_ts: datetime | None = None, latest_ts: datetime | None = None
) -> list[datetime]:
    camera_path = config.output_path / camera

    timestamps: list[datetime] = []

    for image_file in camera_path.iterdir():
        try:
            timestamp = datetime.strptime(
                image_file.name,
                config.output_file_name_format + "." + config.output_file_format,
            ).replace(tzinfo=ZoneInfo("America/St_Johns"))
        except ValueError:
            continue

        if earliest_ts is not None and timestamp < earliest_ts:
            continue
        if latest_ts is not None and timestamp > latest_ts:
            continue

        timestamps.append(timestamp)

    timestamps.sort()

    return timestamps


def get_timestamp_filename(camera: str, timestamp: datetime) -> Path:
    return (
        config.output_path
        / camera
        / timestamp.strftime(
            config.output_file_name_format + "." + config.output_file_format
        )
    )


def create_timelapse(
    camera: str, from_date: datetime, to_date: datetime, output_path: Path
) -> None:
    timestamps = list_camera_timestamps(camera, from_date, to_date)

    if not timestamps:
        raise ValueError("No images found for the specified time range.")

    output_path.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as temp_dir:
        for ts in timestamps:
            shutil.copy(get_timestamp_filename(camera, ts), temp_dir)

        ffmpeg.input(
            str(Path(temp_dir) / ("*." + config.output_file_format)),
            pattern_type="glob",
            framerate=12,
        ).output(str(output_path / f"{camera}.mp4")).run()
