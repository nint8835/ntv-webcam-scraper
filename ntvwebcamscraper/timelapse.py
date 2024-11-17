from datetime import datetime
from zoneinfo import ZoneInfo

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
