import os
import shlex
import tempfile
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import ffmpeg
from sqlalchemy import Select, func, select

from .models import Image

type FrameSelector = Callable[[Select], Select]


def frame_selector_pipeline(*selectors: FrameSelector) -> FrameSelector:
    def pipeline(q: Select) -> Select:
        for selector in selectors:
            q = selector(q)
        return q

    return pipeline


def daily_frames(*, hour: int, frames: int = 1) -> FrameSelector:
    def select_daily_frames(q: Select) -> Select:
        rn = (
            func.row_number()
            .over(
                partition_by=[Image.year, Image.month, Image.day],
                order_by=Image.captured_at,
            )
            .label("rn")
        )
        subq = q.where(Image.hour == hour).add_columns(rn).subquery()
        return (
            select(subq.c.captured_at, subq.c.path)
            .where(subq.c.rn <= frames)
            .order_by(subq.c.captured_at)
        )

    return select_daily_frames


def all_frames(q: Select) -> Select:
    return q


def frame_skip(*, skip: int) -> FrameSelector:
    def select_frame_skip(q: Select) -> Select:
        rn = func.row_number().over(order_by=Image.captured_at).label("rn")
        subq = q.add_columns(rn).subquery()
        return (
            select(subq.c.captured_at, subq.c.path)
            .where((subq.c.rn - 1) % skip == 0)
            .order_by(subq.c.captured_at)
        )

    return select_frame_skip


def _build_concat_file(
    frames: list[tuple[datetime, Path]],
    framerate: int,
) -> str:
    duration = 1 / framerate
    lines = ["ffconcat version 1.0"]
    for ts, image_path in frames:
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

    frames = Image.list_frames(
        camera, from_date, to_date, frame_selector=frame_selector
    )

    if not frames:
        raise ValueError("No images found for the specified time range.")

    output_path.mkdir(parents=True, exist_ok=True)

    concat_content = _build_concat_file(frames, framerate)

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
