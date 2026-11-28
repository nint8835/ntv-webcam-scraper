import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from threading import Event

from fastapi import FastAPI
from scheduler import Scheduler

from ntvwebcamscraper.config import config
from ntvwebcamscraper.database import engine, upgrade_database
from ntvwebcamscraper.web.auth import verifier
from ntvwebcamscraper.web.routers import images
from ntvwebcamscraper.webcams import save_all_camera_images


def run_schedule(schedule: Scheduler, stop: Event) -> None:
    while not stop.is_set():
        schedule.exec_jobs()
        stop.wait(1)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    try:
        if config.init_on_startup:
            await upgrade_database()

        loop = asyncio.get_running_loop()

        def scrape() -> None:
            asyncio.run_coroutine_threadsafe(save_all_camera_images(), loop).result()

        schedule = Scheduler()
        schedule.cyclic(config.interval, scrape)
        stop = Event()
        scraper = asyncio.create_task(asyncio.to_thread(run_schedule, schedule, stop))

        try:
            yield
        finally:
            stop.set()
            await scraper
    finally:
        await verifier.aclose()
        await engine.dispose()


app = FastAPI(lifespan=lifespan)
app.include_router(images.router)
