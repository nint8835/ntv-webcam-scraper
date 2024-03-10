import time

from scheduler import Scheduler

from .config import config
from .webcams import save_all_camera_images

schedule = Scheduler()
schedule.cyclic(config.interval, save_all_camera_images)

while True:
    schedule.exec_jobs()
    time.sleep(1)
