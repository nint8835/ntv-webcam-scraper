from datetime import datetime
from pathlib import Path

from sqlalchemy import DateTime, Integer, UniqueConstraint, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Mapped, mapped_column

from .config import config
from .database import Base, session


class Image(Base):
    __tablename__ = "images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera: Mapped[str]
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    year: Mapped[int]
    month: Mapped[int]
    day: Mapped[int]
    hour: Mapped[int]
    minute: Mapped[int]
    second: Mapped[int]
    weekday: Mapped[int]
    path: Mapped[str]

    __table_args__ = (UniqueConstraint("camera", "captured_at"),)

    @classmethod
    def add(cls, camera: str, timestamp: datetime, path: Path) -> None:
        stmt = (
            insert(cls)
            .values(
                camera=camera,
                captured_at=timestamp,
                year=timestamp.year,
                month=timestamp.month,
                day=timestamp.day,
                hour=timestamp.hour,
                minute=timestamp.minute,
                second=timestamp.second,
                weekday=timestamp.weekday(),
                path=path.as_posix(),
            )
            .on_conflict_do_nothing()
        )
        with session() as s:
            s.execute(stmt)
            s.commit()

    @classmethod
    def list_timestamps(
        cls,
        camera: str,
        earliest_ts: datetime | None = None,
        latest_ts: datetime | None = None,
    ) -> list[datetime]:
        q = select(cls.captured_at).where(cls.camera == camera)

        if earliest_ts is not None:
            q = q.where(cls.captured_at >= earliest_ts)

        if latest_ts is not None:
            q = q.where(cls.captured_at <= latest_ts)

        q = q.order_by(cls.captured_at)

        with session() as s:
            return list(s.scalars(q))

    @classmethod
    def get_path(cls, camera: str, timestamp: datetime) -> Path:
        q = select(cls.path).where(
            cls.camera == camera,
            cls.captured_at == timestamp,
        )
        with session() as s:
            path = s.scalar(q)

        if path is None:
            raise FileNotFoundError(f"No image found for {camera} at {timestamp}")

        return (config.output_path / path).absolute()
