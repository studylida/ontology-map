from functools import lru_cache
from typing import Literal

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ONTOLOGY_MAP_",
        extra="ignore",
    )

    database_url: PostgresDsn
    environment: Literal["development", "test", "production"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
