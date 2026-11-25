from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ntvwebcamscraper.database import async_session


async def get_db() -> AsyncIterator[AsyncSession]:
    """Provide a session for one request. Write endpoints commit explicitly."""
    async with async_session() as db:
        yield db


type DatabaseSession = Annotated[AsyncSession, Depends(get_db)]
