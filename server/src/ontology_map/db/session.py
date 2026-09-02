from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from ontology_map.settings import get_settings


@lru_cache
def get_engine() -> Engine:
    return create_engine(str(get_settings().database_url), pool_pre_ping=True)


def open_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
