import os

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from ontology_map.db.fixture import load_hbf_fixture
from ontology_map.db.ontology_reference_data import (
    ATTRIBUTE_DEFINITIONS,
    RELATION_DEFINITIONS,
    activate_approved_ontology_reference_data,
)
from ontology_map.db.schema import (
    attribute,
    attribute_revision,
    attribute_revision_allowed_unit,
    claim,
    knowledge_item,
    node,
    node_alias,
    node_search_document,
    node_type,
    observation,
    promotion_batch,
    relation,
    relation_endpoint_rule,
    relation_type,
    relation_type_revision,
    source_document,
    topic_reference,
)
from ontology_map.db.session import get_engine
from ontology_map.db.topic_reference_schema import (
    APPROVED_TOPIC_DEFINITIONS,
    PRODUCT_REFERENCE,
)

pytestmark = pytest.mark.skipif(
    os.getenv("ONTOLOGY_MAP_ONTOLOGY_REFERENCE_TEST") != "1",
    reason="#201 전용 실제 PostgreSQL 검증에서 실행한다.",
)


def _count(session: Session, table: sa.Table) -> int:
    return int(session.scalar(sa.select(sa.func.count()).select_from(table)) or 0)


def _force_constraints(session: Session) -> None:
    session.execute(sa.text("SET CONSTRAINTS ALL IMMEDIATE"))
    session.execute(sa.text("SET CONSTRAINTS ALL DEFERRED"))


def _node_type_codes(session: Session) -> dict[int, str]:
    return {
        int(node_type_id): str(code)
        for node_type_id, code in session.execute(
            sa.select(node_type.c.node_type_id, node_type.c.node_type_code)
        )
    }


def _relation_contract(session: Session) -> dict[str, tuple[str, set[tuple[str, str]]]]:
    type_codes = _node_type_codes(session)
    rows = session.execute(
        sa.select(
            relation_type.c.relation_code,
            relation_type_revision.c.relation_type_revision_id,
            relation_type_revision.c.directionality,
        )
        .join(
            relation_type_revision,
            relation_type_revision.c.relation_type_id == relation_type.c.relation_type_id,
        )
        .where(relation_type_revision.c.is_active)
    )
    result: dict[str, tuple[str, set[tuple[str, str]]]] = {}
    for code, revision_id, directionality in rows:
        endpoint_rows = session.execute(
            sa.select(
                relation_endpoint_rule.c.source_node_type_id,
                relation_endpoint_rule.c.target_node_type_id,
            ).where(
                relation_endpoint_rule.c.relation_type_revision_id == revision_id
            )
        )
        pairs = {
            (type_codes[int(source_id)], type_codes[int(target_id)])
            for source_id, target_id in endpoint_rows
        }
        result[str(code)] = str(directionality), pairs
    return result


def _normalized_pairs(
    directionality: str, pairs: set[tuple[str, str]]
) -> set[tuple[str, str]]:
    if directionality != "SYMMETRIC":
        return pairs
    return {tuple(sorted(pair)) for pair in pairs}


def _attribute_contract(
    session: Session,
) -> dict[str, tuple[str, str, set[str]]]:
    type_codes = _node_type_codes(session)
    rows = session.execute(
        sa.select(
            attribute.c.attribute_code,
            attribute_revision.c.attribute_revision_id,
            attribute_revision.c.target_node_type_id,
            attribute_revision.c.allowed_value_kind,
        )
        .join(
            attribute_revision,
            attribute_revision.c.attribute_id == attribute.c.attribute_id,
        )
        .where(attribute_revision.c.is_active)
    )
    result: dict[str, tuple[str, str, set[str]]] = {}
    for code, revision_id, target_id, value_kind in rows:
        units = {
            str(unit)
            for unit in session.scalars(
                sa.select(attribute_revision_allowed_unit.c.unit_code).where(
                    attribute_revision_allowed_unit.c.attribute_revision_id
                    == revision_id
                )
            )
        }
        result[str(code)] = (
            type_codes[int(target_id)],
            str(value_kind),
            units,
        )
    return result


def test_clean_activation_is_exact_and_idempotent() -> None:
    engine = get_engine()
    with engine.connect() as connection:
        outer = connection.begin()
        try:
            with Session(bind=connection) as session:
                with session.begin():
                    first = activate_approved_ontology_reference_data(session)
                    _force_constraints(session)
                    second = activate_approved_ontology_reference_data(session)
                    _force_constraints(session)

                    assert first == second
                    assert len(first.relation_revision_ids) == 14
                    assert len(first.attribute_revision_ids) == 6
                    assert len(first.topic_node_ids) == 9

                    relation_contract = _relation_contract(session)
                    assert set(relation_contract) == {
                        definition.code for definition in RELATION_DEFINITIONS
                    }
                    for definition in RELATION_DEFINITIONS:
                        actual_direction, actual_pairs = relation_contract[definition.code]
                        assert actual_direction == definition.directionality
                        assert _normalized_pairs(actual_direction, actual_pairs) == (
                            _normalized_pairs(
                                definition.directionality,
                                set(definition.endpoint_pairs),
                            )
                        )

                    assert relation_contract["RELATED_TO"] == (
                        "SYMMETRIC",
                        {("TECHNOLOGY", "EVENT")},
                    )
                    assert relation_contract["HAS_TOPIC"][0] == "DIRECTED"
                    assert relation_contract["HAS_TOPIC"][1] == {
                        ("COMPANY", "TOPIC"),
                        ("PERSON", "TOPIC"),
                        ("TECHNOLOGY", "TOPIC"),
                        ("EVENT", "TOPIC"),
                    }

                    attribute_contract = _attribute_contract(session)
                    assert set(attribute_contract) == {
                        definition.code for definition in ATTRIBUTE_DEFINITIONS
                    }
                    assert attribute_contract["CORE_COUNT"] == (
                        "TECHNOLOGY",
                        "NUMBER",
                        {"COUNT"},
                    )
                    assert attribute_contract["MAX_MEMORY_BANDWIDTH"] == (
                        "TECHNOLOGY",
                        "NUMBER",
                        {"GB_PER_S", "TB_PER_S"},
                    )
                    for code in (
                        "ROLE_TITLE",
                        "TECHNOLOGY_VERSION",
                        "COMMERCIALIZATION_STATUS",
                        "COMMERCIALIZATION_SCHEDULE",
                    ):
                        assert attribute_contract[code][2] == set()

                    topic_rows = session.execute(
                        sa.select(
                            topic_reference.c.node_id,
                            topic_reference.c.topic_code,
                            topic_reference.c.canonical_display_name,
                            topic_reference.c.is_active,
                            knowledge_item.c.lifecycle_kind,
                            knowledge_item.c.current_state,
                            knowledge_item.c.promotion_batch_id,
                            node_type.c.node_type_code,
                        )
                        .join(node, node.c.node_id == topic_reference.c.node_id)
                        .join(node_type, node_type.c.node_type_id == node.c.node_type_id)
                        .join(
                            knowledge_item,
                            knowledge_item.c.knowledge_item_id == topic_reference.c.node_id,
                        )
                        .order_by(topic_reference.c.topic_code)
                    ).all()
                    assert {
                        (str(code), str(name))
                        for _node_id, code, name, *_rest in topic_rows
                    } == set(APPROVED_TOPIC_DEFINITIONS)
                    assert all(bool(row.is_active) for row in topic_rows)
                    assert all(row.lifecycle_kind == PRODUCT_REFERENCE for row in topic_rows)
                    assert all(row.current_state is None for row in topic_rows)
                    assert all(row.promotion_batch_id is None for row in topic_rows)
                    assert all(row.node_type_code == "TOPIC" for row in topic_rows)

                    assert _count(session, source_document) == 0
                    assert _count(session, observation) == 0
                    assert _count(session, promotion_batch) == 0
                    assert _count(session, claim) == 0
                    assert _count(session, relation) == 0
                    assert _count(session, node_alias) == 0
                    assert _count(session, node_search_document) == 0
        finally:
            outer.rollback()


def test_activation_preserves_hbf_fixture_and_existing_knowledge() -> None:
    created, fixture_node_ids = load_hbf_fixture()
    assert created

    engine = get_engine()
    with Session(engine) as session:
        dev_relation_type_id = int(
            session.scalar(
                sa.select(relation_type.c.relation_type_id).where(
                    relation_type.c.relation_code == "PUBLICLY_ASSOCIATED_WITH"
                )
            )
        )
        dev_revision_id = int(
            session.scalar(
                sa.select(relation_type_revision.c.relation_type_revision_id).where(
                    relation_type_revision.c.relation_type_id == dev_relation_type_id,
                    relation_type_revision.c.is_active,
                )
            )
        )
        before = {
            "relation": _count(session, relation),
            "claim": _count(session, claim),
            "source_document": _count(session, source_document),
            "observation": _count(session, observation),
            "promotion_batch": _count(session, promotion_batch),
            "node_search_document": _count(session, node_search_document),
        }

    with Session(engine) as session:
        with session.begin():
            result = activate_approved_ontology_reference_data(session)
            _force_constraints(session)

    with Session(engine) as session:
        assert session.scalar(
            sa.select(relation_type.c.relation_type_id).where(
                relation_type.c.relation_code == "PUBLICLY_ASSOCIATED_WITH"
            )
        ) == dev_relation_type_id
        assert session.scalar(
            sa.select(relation_type_revision.c.relation_type_revision_id).where(
                relation_type_revision.c.relation_type_id == dev_relation_type_id,
                relation_type_revision.c.is_active,
            )
        ) == dev_revision_id
        assert {
            "relation": _count(session, relation),
            "claim": _count(session, claim),
            "source_document": _count(session, source_document),
            "observation": _count(session, observation),
            "promotion_batch": _count(session, promotion_batch),
            "node_search_document": _count(session, node_search_document),
        } == before
        assert _count(session, topic_reference) == 9
        assert len(result.topic_node_ids) == 9
        assert not set(fixture_node_ids.values()) & set(result.topic_node_ids.values())

    created_again, fixture_node_ids_again = load_hbf_fixture()
    assert not created_again
    assert fixture_node_ids_again == fixture_node_ids
