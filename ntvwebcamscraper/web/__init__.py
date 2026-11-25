import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from threading import Event

from fastapi import FastAPI
from scheduler import Scheduler

from ntvwebcamscraper.config import config
from ntvwebcamscraper.database import upgrade_database
from ntvwebcamscraper.webcams import save_all_camera_images


def run_schedule(schedule: Scheduler, stop: Event) -> None:
    while not stop.is_set():
        schedule.exec_jobs()
        stop.wait(1)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    if config.init_on_startup:
        await asyncio.to_thread(upgrade_database)

    schedule = Scheduler()
    schedule.cyclic(config.interval, save_all_camera_images)
    stop = Event()
    scraper = asyncio.create_task(asyncio.to_thread(run_schedule, schedule, stop))

    try:
        yield
    finally:
        stop.set()
        await scraper


app = FastAPI(lifespan=lifespan, openapi_url=None, docs_url=None, redoc_url=None)
