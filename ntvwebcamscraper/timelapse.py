import tempfile
from datetime import datetime
from itertools import groupby
from pathlib import Path
from zoneinfo import ZoneInfo

import ffmpeg

from .config import config


def list_camera_timestamps(
    camera: str, earliest_ts: datetime | None = None, latest_ts: datetime | None = None
) -> list[datetime]:
    camera_path = config.output_path / camera

    timestamps: list[datetime] = []

    for date_folder in camera_path.iterdir():
        if not date_folder.is_dir():
            continue
            
        for image_file in date_folder.iterdir():
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
    date_folder = timestamp.strftime("%Y-%m-%d")
    return (
        config.output_path
        / camera
        / date_folder
        / timestamp.strftime(
            config.output_file_name_format + "." + config.output_file_format
        )
    ).absolute()


type FrameSelector = callable[[list[datetime]], list[datetime]]


def frame_selector_pipeline(*selectors: FrameSelector) -> FrameSelector:
    def pipeline(timestamps: list[datetime]) -> list[datetime]:
        for selector in selectors:
            timestamps = selector(timestamps)

        return timestamps

    return pipeline


def daily_frames(*, hour: int, frames: int = 1) -> FrameSelector:
    def select_daily_frames(timestamps: list[datetime]) -> list[datetime]:
        grouped = groupby(timestamps, key=lambda ts: ts.toordinal())

        daily_frames = []

        for _, timestamps in grouped:
            hour_frames = [ts for ts in timestamps if ts.hour == hour]
            daily_frames.extend(hour_frames[:frames])

        return daily_frames

    return select_daily_frames


def all_frames(timestamps: list[datetime]) -> list[datetime]:
    return timestamps


def frame_skip(*, skip: int) -> FrameSelector:
    def select_frame_skip(timestamps: list[datetime]) -> list[datetime]:
        return timestamps[::skip]

    return select_frame_skip


def create_timelapse(
    *,
    camera: str,
    from_date: datetime,
    to_date: datetime,
    output_path: Path,
    framerate: int,
    include_timestamp: bool,
    frame_selector: FrameSelector = all_frames,
) -> None:
    print(f"Creating timelapse for {camera} from {from_date} to {to_date}")

    timestamps = list_camera_timestamps(camera, from_date, to_date)
    target_timestamps = frame_selector(timestamps)

    if not timestamps:
        raise ValueError("No images found for the specified time range.")

    output_path.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        for ts in target_timestamps:
            timestamp_path = get_timestamp_filename(camera, ts)
            (temp_dir_path / timestamp_path.name).symlink_to(timestamp_path)

        pipeline = ffmpeg.input(
            str(temp_dir_path / ("*." + config.output_file_format)),
            pattern_type="glob",
            framerate=framerate,
            export_path_metadata=1,
        )

        if include_timestamp:
            pipeline = pipeline.drawtext(
                text="%{metadata:lavf.image2dec.source_basename}",
                escape_text=False,
                x=10,
                y=10,
                fontsize=20,
                borderw=2,
                bordercolor="white",
            )

        try:
            pipeline.output(
                str(output_path / f"{camera}.mp4"),
            ).run(
                overwrite_output=True,
                capture_stdout=True,
                capture_stderr=True,
            )
        except ffmpeg.Error as e:
            raise RuntimeError(f"ffmpeg error: {e.stderr.decode()}") from e
