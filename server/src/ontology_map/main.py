from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from sqlalchemy import text

from ontology_map.api import (
    APIError,
    api_error_handler,
    router,
    validation_error_handler,
)
from ontology_map.db.session import get_engine
from ontology_map.settings import get_settings


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1"))
    yield


def create_app() -> FastAPI:
    get_settings()
    application = FastAPI(title="ontology-map API", version="1.0.0", lifespan=lifespan)
    application.add_exception_handler(APIError, api_error_handler)
    application.add_exception_handler(RequestValidationError, validation_error_handler)
    application.include_router(router)
    return application


app = create_app()
