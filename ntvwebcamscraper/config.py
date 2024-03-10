from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ntvwebcamscraper_")

    output_path: Path = Path("images")


config = Config()

__all__ = ["config"]
