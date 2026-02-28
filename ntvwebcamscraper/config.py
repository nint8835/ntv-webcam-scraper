from datetime import timedelta
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ntvwebcamscraper_")

    output_path: Path = Path("images")
    output_file_name_format: str = "%Y-%m-%d %H-%M-%S"
    output_file_format: str = "jpg"
    interval: timedelta = timedelta(minutes=5)
    db_filename: str = "images.db"
    init_on_startup: bool = True

    target_cameras: Optional[list[str]] = None
    excluded_cameras: list[str] = []

    @property
    def db_uri(self) -> str:
        return f"sqlite:///{self.output_path / self.db_filename}"


config = Config()

__all__ = ["config"]
