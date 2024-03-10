from .webcams import (
    list_cameras,
    save_camera_image,
)

cameras = list_cameras()

for camera in cameras:
    save_camera_image(camera)
