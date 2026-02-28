import os
import shlex
import tempfile
from datetime import datetime
from itertools import groupby
from pathlib import Path

import ffmpeg

from .models import Image

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


def _build_concat_file(
    target_timestamps: list[datetime],
    camera: str,
    framerate: int,
) -> str:
    duration = 1 / framerate
    lines = ["ffconcat version 1.0"]
    for ts in target_timestamps:
        image_path = Image.get_path(camera, ts)
        lines.append(f"file {shlex.quote(image_path.as_posix())}")
        lines.append(f"duration {duration:.10f}")
        lines.append(f"file_packet_metadata title='{ts.strftime('%Y-%m-%d %H:%M:%S')}'")
    return "\n".join(lines) + "\n"


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

    timestamps = Image.list_timestamps(camera, from_date, to_date)
    target_timestamps = frame_selector(timestamps)

    if not timestamps:
        raise ValueError("No images found for the specified time range.")

    output_path.mkdir(parents=True, exist_ok=True)

    concat_content = _build_concat_file(target_timestamps, camera, framerate)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        f.write(concat_content)
        concat_file_path = f.name

    try:
        pipeline = ffmpeg.input(
            concat_file_path,
            format="concat",
            safe=0,
        )

        if include_timestamp:
            pipeline = pipeline.drawtext(
                text="%{metadata:title}",
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
    finally:
        os.unlink(concat_file_path)
