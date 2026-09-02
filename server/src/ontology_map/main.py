from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from ontology_map.db.session import get_engine
from ontology_map.settings import get_settings


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1"))
    yield


def create_app() -> FastAPI:
    get_settings()
    return FastAPI(title="ontology-map API", version="1.0.0", lifespan=lifespan)


app = create_app()
