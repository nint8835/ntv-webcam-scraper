import asyncio
from collections.abc import Awaitable, Callable
from functools import wraps

from ntvwebcamscraper.database import engine


def async_command[**P, R](command: Callable[P, Awaitable[R]]) -> Callable[P, R]:
    @wraps(command)
    def run(*args: P.args, **kwargs: P.kwargs) -> R:
        async def execute() -> R:
            try:
                return await command(*args, **kwargs)
            finally:
                await engine.dispose()

        return asyncio.run(execute())

    return run
