import sqlite3
from datetime import datetime
from pathlib import Path

from .config import config

_SCHEMA = """
    CREATE TABLE IF NOT EXISTS images (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        camera      TEXT NOT NULL,
        captured_at DATETIME NOT NULL,
        year        INTEGER NOT NULL,
        month       INTEGER NOT NULL,
        day         INTEGER NOT NULL,
        hour        INTEGER NOT NULL,
        minute      INTEGER NOT NULL,
        second      INTEGER NOT NULL,
        weekday     INTEGER NOT NULL,
        path        TEXT NOT NULL,
        UNIQUE(camera, captured_at)
    );
    CREATE INDEX IF NOT EXISTS idx_camera_captured_at  ON images(camera, captured_at);
    CREATE INDEX IF NOT EXISTS idx_camera_date         ON images(camera, year, month, day);
    CREATE INDEX IF NOT EXISTS idx_camera_weekday_hour ON images(camera, weekday, hour);
"""


class Database:
    def __init__(self) -> None:
        self._conn: sqlite3.Connection | None = None
        self._initialized: bool = False

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            db_path = config.output_path / "images.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def init_db(self) -> None:
        conn = self._get_conn()
        conn.executescript(_SCHEMA)
        conn.commit()
        self._initialized = True
        self.merge_pending_migration()

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            self.init_db()

    def add_image(self, camera: str, timestamp: datetime, path: Path) -> None:
        self._ensure_initialized()
        conn = self._get_conn()
        conn.execute(
            """
            INSERT OR IGNORE INTO images
                (camera, captured_at, year, month, day, hour, minute, second, weekday, path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                camera,
                timestamp.isoformat(),
                timestamp.year,
                timestamp.month,
                timestamp.day,
                timestamp.hour,
                timestamp.minute,
                timestamp.second,
                timestamp.weekday(),
                path.as_posix(),
            ),
        )
        conn.commit()

    def list_camera_timestamps(
        self,
        camera: str,
        earliest_ts: datetime | None = None,
        latest_ts: datetime | None = None,
    ) -> list[datetime]:
        self._ensure_initialized()
        conn = self._get_conn()

        query = "SELECT captured_at FROM images WHERE camera = ?"
        params: list = [camera]

        if earliest_ts is not None:
            params.append(earliest_ts.isoformat())
            query += " AND captured_at >= ?"

        if latest_ts is not None:
            params.append(latest_ts.isoformat())
            query += " AND captured_at <= ?"

        query += " ORDER BY captured_at"

        rows = conn.execute(query, params).fetchall()
        return [datetime.fromisoformat(row[0]) for row in rows]

    def get_image_path(self, camera: str, timestamp: datetime) -> Path:
        self._ensure_initialized()
        conn = self._get_conn()

        row = conn.execute(
            "SELECT path FROM images WHERE camera = ? AND captured_at = ?",
            (camera, timestamp.isoformat()),
        ).fetchone()

        if row is None:
            raise FileNotFoundError(f"No image found for {camera} at {timestamp}")

        return (config.output_path / row[0]).absolute()

    def merge_from(self, source_db_path: Path) -> None:
        self._ensure_initialized()
        conn = self._get_conn()
        conn.execute("ATTACH DATABASE ? AS source", (str(source_db_path),))
        conn.execute("""
            INSERT OR IGNORE INTO images
                (camera, captured_at, year, month, day, hour, minute, second, weekday, path)
            SELECT camera, captured_at, year, month, day, hour, minute, second, weekday, path
            FROM source.images
        """)
        conn.commit()
        conn.execute("DETACH DATABASE source")

    def merge_pending_migration(self) -> None:
        migration_db_path = config.output_path / "migration.db"
        if migration_db_path.exists():
            print("Found migration.db, merging...")
            self.merge_from(migration_db_path)
            migration_db_path.unlink()
            print("Migration merged and migration.db deleted.")


db = Database()
