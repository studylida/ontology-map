import os

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from ontology_map.db.session import get_engine
from ontology_map.db.topic_references import (
    ensure_topic_reference,
    list_topic_references,
)

pytestmark = pytest.mark.skipif(
    os.getenv("ONTOLOGY_MAP_TOPIC_REFERENCE_TEST") != "1",
    reason="#206 Topic list 실제 PostgreSQL 검증에서 실행한다.",
)


def test_topic_list_read_keeps_active_and_inactive_reference_rows() -> None:
    with get_engine().connect() as connection:
        transaction = connection.begin()
        try:
            with Session(bind=connection) as session:
                session.execute(sa.text("SELECT 1"))
                first = ensure_topic_reference(
                    session,
                    topic_code="SEMICONDUCTOR",
                    canonical_display_name="반도체",
                    is_active=True,
                )
                second = ensure_topic_reference(
                    session,
                    topic_code="INVESTMENT",
                    canonical_display_name="투자",
                    is_active=False,
                )

                rows = list_topic_references(session)
                selected = {row.node_id: row for row in rows}

                assert selected[first.node_id].canonical_display_name == "반도체"
                assert selected[first.node_id].is_active is True
                assert selected[second.node_id].canonical_display_name == "투자"
                assert selected[second.node_id].is_active is False
        finally:
            transaction.rollback()
