import asyncio

import alembic.config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import config


class Base(DeclarativeBase):
    pass


engine = create_async_engine(config.async_db_uri)
async_session = async_sessionmaker(engine, expire_on_commit=False)


async def upgrade_database() -> None:
    config.output_path.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(alembic.config.main, argv=["--raiseerr", "upgrade", "head"])
    await merge_pending_migration()


async def merge_pending_migration() -> None:
    migration_db_path = config.output_path / "migration.db"
    if not migration_db_path.exists():
        return

    print("Found migration.db, merging...")
    async with engine.connect() as conn:
        try:
            await conn.execute(
                text("ATTACH DATABASE :path AS source"),
                {"path": str(migration_db_path)},
            )
            await conn.execute(
                text("""
                INSERT OR IGNORE INTO images
                    (camera, captured_at, year, month, day, hour, minute, second, weekday, path)
                SELECT camera, captured_at, year, month, day, hour, minute, second, weekday, path
                FROM source.images
                """)
            )
            await conn.commit()
            await conn.execute(text("DETACH DATABASE source"))
        except BaseException:
            # A failed merge can leave the source attached to the connection.
            await conn.invalidate()
            raise
    migration_db_path.unlink()

    print("Migration database merged.")
