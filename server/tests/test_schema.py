import sqlalchemy as sa
from sqlalchemy import Inspector

from ontology_map.db.schema import metadata
from ontology_map.db.session import get_engine

DEFERRED_TABLES = {"knowledge_state_event", "conflict_state_event"}


def _assert_named_schema_objects(inspector: Inspector) -> None:
    for table in metadata.sorted_tables:
        table_name = table.name
        assert inspector.get_pk_constraint(table_name)["name"] == table.primary_key.name

        actual_foreign_keys = {
            constraint["name"] for constraint in inspector.get_foreign_keys(table_name)
        }
        expected_foreign_keys = {
            constraint.name
            for constraint in table.foreign_key_constraints
            if constraint.name is not None
        }
        assert expected_foreign_keys <= actual_foreign_keys

        actual_unique_constraints = {
            constraint["name"]
            for constraint in inspector.get_unique_constraints(table_name)
        }
        expected_unique_constraints = {
            constraint.name
            for constraint in table.constraints
            if isinstance(constraint, sa.UniqueConstraint)
            and constraint.name is not None
        }
        assert expected_unique_constraints <= actual_unique_constraints

        actual_checks = {
            constraint["name"]
            for constraint in inspector.get_check_constraints(table_name)
        }
        expected_checks = {
            constraint.name
            for constraint in table.constraints
            if isinstance(constraint, sa.CheckConstraint)
            and constraint.name is not None
        }
        assert expected_checks <= actual_checks

        actual_indexes = {index["name"] for index in inspector.get_indexes(table_name)}
        expected_indexes = {index.name for index in table.indexes}
        assert expected_indexes <= actual_indexes

        assert inspector.get_table_comment(table_name)["text"]
        actual_columns = {
            column["name"]: column for column in inspector.get_columns(table_name)
        }
        for column in table.columns:
            if column.comment is not None:
                assert actual_columns[column.name]["comment"] == column.comment


def test_frozen_schema_inventory_and_named_objects() -> None:
    inspector = sa.inspect(get_engine())
    application_tables = set(inspector.get_table_names()) - {"alembic_version"}

    assert application_tables == set(metadata.tables)
    assert len(application_tables) == 43
    assert application_tables.isdisjoint(DEFERRED_TABLES)
    _assert_named_schema_objects(inspector)


def test_postgresql_vector_and_fts_contract() -> None:
    with get_engine().connect() as connection:
        server_version = connection.scalar(sa.text("SHOW server_version"))
        vector_version = connection.scalar(
            sa.text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        )
        vector_type = connection.scalar(
            sa.text(
                """
                SELECT format_type(attribute.atttypid, attribute.atttypmod)
                FROM pg_attribute AS attribute
                JOIN pg_class AS relation_class
                  ON relation_class.oid = attribute.attrelid
                WHERE relation_class.relname = 'node_embedding'
                  AND attribute.attname = 'embedding_vector'
                """
            )
        )
        fts_index = connection.scalar(
            sa.text(
                """
                SELECT indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename = 'node_search_document'
                  AND indexname = 'ix_node_search_document__fts'
                """
            )
        )

    assert str(server_version).startswith("18.6")
    assert vector_version == "0.8.6"
    assert vector_type == "vector(1024)"
    assert fts_index is not None
    assert "USING gin" in fts_index
    assert "to_tsvector('simple'::regconfig, identity_text)" in fts_index
    assert "to_tsvector('simple'::regconfig, knowledge_text)" in fts_index
    assert "setweight" in fts_index
