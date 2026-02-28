from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import config


class Base(DeclarativeBase):
    pass


engine = create_engine(config.db_uri)
session = sessionmaker(engine, expire_on_commit=False)


def merge_pending_migration() -> None:
    migration_db_path = config.output_path / "migration.db"
    if not migration_db_path.exists():
        return

    print("Found migration.db, merging...")
    with engine.connect() as conn:
        conn.execute(
            text("ATTACH DATABASE :path AS source"), {"path": str(migration_db_path)}
        )
        conn.execute(
            text("""
            INSERT OR IGNORE INTO images
                (camera, captured_at, year, month, day, hour, minute, second, weekday, path)
            SELECT camera, captured_at, year, month, day, hour, minute, second, weekday, path
            FROM source.images
        """)
        )
        conn.commit()
        conn.execute(text("DETACH DATABASE source"))
    migration_db_path.unlink()

    print("Migration database merged.")
