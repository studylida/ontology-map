"""Issue #216 regression tests against an isolated migrated PostgreSQL database."""

import os
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from threading import Barrier
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ontology_map.db import promotion_provenance as provenance

DATABASE_URL = os.environ.get("ONTOLOGY_MAP_PROMOTION_PROVENANCE_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="isolated migrated PostgreSQL URL was not supplied",
)


def execute(session: Session, sql: str, **values: object) -> sa.Result[object]:
    return session.execute(sa.text(sql), values)


def returning(session: Session, sql: str, **values: object) -> int:
    return int(execute(session, sql, **values).scalar_one())


def _checked_url() -> sa.URL:
    url = sa.engine.make_url(DATABASE_URL)
    assert url.get_backend_name() == "postgresql"
    assert url.host in {"localhost", "127.0.0.1", "::1"}
    assert url.database and url.database.endswith("_promotion216_test")
    return url


def _policy(session: Session) -> int:
    return returning(
        session,
        """
        INSERT INTO lint_policy_version (version_no, validator_version, is_active)
        SELECT coalesce(max(version_no), 0) + 1, :validator, false
        FROM lint_policy_version
        RETURNING lint_policy_version_id
        """,
        validator=f"promotion216-{uuid4()}",
    )


def _batch(
    session: Session,
    *,
    committed: bool = False,
    ready: bool = False,
) -> int:
    policy = _policy(session)
    if ready:
        return returning(
            session,
            """
            INSERT INTO promotion_batch (
                lint_policy_version_id, promotion_status, publication_status,
                committed_at, ready_at
            ) VALUES (
                :policy, 'COMMITTED', 'READY',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            RETURNING promotion_batch_id
            """,
            policy=policy,
        )
    if committed:
        return returning(
            session,
            """
            INSERT INTO promotion_batch (
                lint_policy_version_id, promotion_status, committed_at
            ) VALUES (:policy, 'COMMITTED', CURRENT_TIMESTAMP)
            RETURNING promotion_batch_id
            """,
            policy=policy,
        )
    return returning(
        session,
        """
        INSERT INTO promotion_batch (lint_policy_version_id)
        VALUES (:policy) RETURNING promotion_batch_id
        """,
        policy=policy,
    )


def _node_type(session: Session, code: str) -> int:
    execute(
        session,
        """
        INSERT INTO node_type (node_type_code, display_name, creation_rule, is_active)
        VALUES (:code, :code, 'issue 216 regression', true)
        ON CONFLICT (node_type_code) DO UPDATE SET is_active = true
        """,
        code=code,
    )
    return int(
        execute(
            session,
            "SELECT node_type_id FROM node_type WHERE node_type_code = :code",
            code=code,
        ).scalar_one()
    )


def _node(
    session: Session,
    base_batch: int,
    *,
    code: str = "COMPANY",
) -> int:
    type_id = _node_type(session, code)
    node_id = returning(
        session,
        """
        INSERT INTO knowledge_item (item_kind, current_state, promotion_batch_id)
        VALUES ('NODE', 'EVIDENCE_VERIFIED', :batch_id)
        RETURNING knowledge_item_id
        """,
        batch_id=base_batch,
    )
    execute(
        session,
        "INSERT INTO node (node_id, node_type_id) VALUES (:node_id, :type_id)",
        node_id=node_id,
        type_id=type_id,
    )
    return node_id


def _claim(session: Session, base_batch: int, text: str | None = None) -> int:
    claim_id = returning(
        session,
        """
        INSERT INTO knowledge_item (item_kind, current_state, promotion_batch_id)
        VALUES ('CLAIM', 'EVIDENCE_VERIFIED', :batch_id)
        RETURNING knowledge_item_id
        """,
        batch_id=base_batch,
    )
    execute(
        session,
        """
        INSERT INTO claim (
            claim_id, statement_text, language, modality,
            asserted_from_precision, asserted_to_precision
        ) VALUES (
            :claim_id, :text, 'ko', 'FACT', 'UNKNOWN', 'UNKNOWN'
        )
        """,
        claim_id=claim_id,
        text=text or f"issue 216 claim {uuid4()}",
    )
    return claim_id


def _observation(session: Session, body: str | None = None) -> int:
    text = body or f"issue 216 evidence {uuid4()}"
    group_id = returning(
        session,
        "INSERT INTO evidence_group DEFAULT VALUES RETURNING evidence_group_id",
    )
    document_id = returning(
        session,
        """
        INSERT INTO source_document (
            evidence_group_id, source_key, version_no, canonical_url,
            publisher_name, title, original_language, normalized_body, body_hash,
            published_precision, modified_precision, last_checked_at, last_check_status
        ) VALUES (
            :group_id, :source_key, 1, :url,
            'issue216', 'issue216', 'ko', :body, :body_hash,
            'UNKNOWN', 'UNKNOWN', CURRENT_TIMESTAMP, 'SUCCESS'
        )
        RETURNING source_document_id
        """,
        group_id=group_id,
        source_key=f"promotion216:{uuid4()}",
        url=f"https://example.invalid/{uuid4()}",
        body=text,
        body_hash=sha256(text.encode()).digest(),
    )
    return returning(
        session,
        """
        INSERT INTO observation (
            source_document_id, start_char, end_char,
            quote_text, quote_hash, observed_at
        ) VALUES (
            :document_id, 0, :end_char, :body, :quote_hash, CURRENT_TIMESTAMP
        )
        RETURNING observation_id
        """,
        document_id=document_id,
        end_char=len(text),
        body=text,
        quote_hash=sha256(text.encode()).digest(),
    )


def _relation_revision(session: Session, type_id: int) -> int:
    relation_code = f"PROMOTION_216_{uuid4().hex}"
    relation_type_id = returning(
        session,
        """
        INSERT INTO relation_type (relation_code)
        VALUES (:code) RETURNING relation_type_id
        """,
        code=relation_code,
    )
    revision_id = returning(
        session,
        """
        INSERT INTO relation_type_revision (
            relation_type_id, version_no, display_name, directionality, is_active
        ) VALUES (
            :relation_type_id, 1, 'issue 216 relation', 'DIRECTED', true
        )
        RETURNING relation_type_revision_id
        """,
        relation_type_id=relation_type_id,
    )
    execute(
        session,
        """
        INSERT INTO relation_endpoint_rule (
            relation_type_revision_id, source_node_type_id, target_node_type_id
        ) VALUES (:revision, :type_id, :type_id)
        """,
        revision=revision_id,
        type_id=type_id,
    )
    return revision_id


def _relation(
    session: Session,
    base_batch: int,
    source_node_id: int,
    target_node_id: int,
) -> int:
    type_id = int(
        execute(
            session,
            "SELECT node_type_id FROM node WHERE node_id = :node_id",
            node_id=source_node_id,
        ).scalar_one()
    )
    revision_id = _relation_revision(session, type_id)
    relation_id = returning(
        session,
        """
        INSERT INTO knowledge_item (item_kind, current_state, promotion_batch_id)
        VALUES ('RELATION', 'EVIDENCE_VERIFIED', :batch_id)
        RETURNING knowledge_item_id
        """,
        batch_id=base_batch,
    )
    execute(
        session,
        """
        INSERT INTO relation (
            relation_id, source_node_id, target_node_id,
            relation_type_revision_id, relation_identity_key
        ) VALUES (
            :relation_id, :source_node_id, :target_node_id,
            :revision_id, :identity_key
        )
        """,
        relation_id=relation_id,
        source_node_id=source_node_id,
        target_node_id=target_node_id,
        revision_id=revision_id,
        identity_key=sha256(f"relation:{uuid4()}".encode()).digest(),
    )
    return relation_id


def _attribute_revision(session: Session, target_type_id: int) -> int:
    attribute_id = returning(
        session,
        """
        INSERT INTO attribute (attribute_code)
        VALUES (:code) RETURNING attribute_id
        """,
        code=f"PROMOTION_216_{uuid4().hex}",
    )
    return returning(
        session,
        """
        INSERT INTO attribute_revision (
            attribute_id, version_no, display_name,
            target_node_type_id, allowed_value_kind, is_active
        ) VALUES (
            :attribute_id, 1, 'issue 216 attribute',
            :target_type_id, 'STRING', true
        )
        RETURNING attribute_revision_id
        """,
        attribute_id=attribute_id,
        target_type_id=target_type_id,
    )


@pytest.fixture
def database() -> Session:
    engine = sa.create_engine(_checked_url())
    with engine.connect() as connection:
        outer = connection.begin()
        try:
            with Session(bind=connection) as session:
                yield session
        finally:
            outer.rollback()
    engine.dispose()


def _base_objects(session: Session) -> dict[str, int]:
    base_batch = _batch(session, ready=True)
    left = _node(session, base_batch)
    right = _node(session, base_batch)
    third = _node(session, base_batch)
    event = _node(session, base_batch, code="EVENT")
    claim = _claim(session, base_batch)
    relation = _relation(session, base_batch, left, right)
    observation = _observation(session)
    execute(
        session,
        """
        INSERT INTO event_temporal_extent (
            event_node_id, start_at, end_at, start_precision, end_precision
        ) VALUES (:event_node_id, NULL, NULL, 'UNKNOWN', 'UNKNOWN')
        """,
        event_node_id=event,
    )
    type_id = int(
        execute(
            session,
            "SELECT node_type_id FROM node WHERE node_id = :node_id",
            node_id=left,
        ).scalar_one()
    )
    attribute_revision = _attribute_revision(session, type_id)
    return {
        "base_batch": base_batch,
        "left": left,
        "right": right,
        "third": third,
        "event": event,
        "claim": claim,
        "relation": relation,
        "observation": observation,
        "attribute_revision": attribute_revision,
    }


def test_schema_rejects_unknown_kind_bad_shape_and_nonexistent_association(
    database: Session,
) -> None:
    values = _base_objects(database)
    batch_id = _batch(database)
    alias_id = returning(
        database,
        """
        INSERT INTO node_alias (node_id, alias_text, language, is_preferred)
        VALUES (:node_id, :text, 'ko', false)
        RETURNING node_alias_id
        """,
        node_id=values["left"],
        text=f"alias-{uuid4()}",
    )

    with pytest.raises(IntegrityError):
        with database.begin_nested():
            execute(
                database,
                """
                INSERT INTO promotion_canonical_change (
                    promotion_batch_id, change_kind, node_alias_id
                ) VALUES (:batch, 'UNKNOWN_KIND', :alias_id)
                """,
                batch=batch_id,
                alias_id=alias_id,
            )

    with pytest.raises(IntegrityError):
        with database.begin_nested():
            execute(
                database,
                """
                INSERT INTO promotion_canonical_change (
                    promotion_batch_id, change_kind, node_alias_id, observation_id
                ) VALUES (
                    :batch, 'NODE_ALIAS_CHANGED', :alias_id, :observation_id
                )
                """,
                batch=batch_id,
                alias_id=alias_id,
                observation_id=values["observation"],
            )

    with pytest.raises(IntegrityError):
        with database.begin_nested():
            execute(
                database,
                """
                INSERT INTO promotion_canonical_change (
                    promotion_batch_id, change_kind, node_alias_id, observation_id
                ) VALUES (
                    :batch, 'NODE_ALIAS_EVIDENCE_ADDED', :alias_id, :observation_id
                )
                """,
                batch=batch_id,
                alias_id=alias_id,
                observation_id=values["observation"],
            )

    indexes = execute(
        database,
        """
        SELECT indexname, indexdef
        FROM pg_indexes
        WHERE schemaname = 'public'
          AND tablename = 'promotion_canonical_change'
          AND indexname LIKE 'uq_promotion_canonical_change__%'
        ORDER BY indexname
        """,
    ).all()
    assert len(indexes) == 6
    assert all(
        "UNIQUE INDEX" in row.indexdef and " WHERE " in row.indexdef for row in indexes
    )

    definitions = {
        row.conname: row.definition
        for row in execute(
            database,
            """
            SELECT conname, pg_get_constraintdef(oid) AS definition
            FROM pg_constraint
            WHERE conrelid = 'promotion_canonical_change'::regclass
            """,
        ).all()
    }
    expected_foreign_targets = {
        "fk_promotion_canonical_change__promotion_batch": "REFERENCES promotion_batch(promotion_batch_id)",
        "fk_promotion_canonical_change__node_alias": "REFERENCES node_alias(node_alias_id)",
        "fk_promotion_canonical_change__node_alias_evidence": "REFERENCES node_alias_evidence(node_alias_id, observation_id)",
        "fk_promotion_canonical_change__claim_observation": "REFERENCES claim_observation(claim_id, observation_id)",
        "fk_promotion_canonical_change__claim_relation": "REFERENCES claim_relation(claim_id, relation_id)",
        "fk_promotion_canonical_change__attribute_value": "REFERENCES claim_attribute_value(claim_attribute_value_id)",
        "fk_promotion_canonical_change__event_temporal_basis": "REFERENCES event_temporal_basis(event_node_id, claim_id)",
    }
    for name, target in expected_foreign_targets.items():
        assert name in definitions
        assert target.replace(" ", "") in definitions[name].replace(" ", "")

    batch_index = execute(
        database,
        """
        SELECT indexdef FROM pg_indexes
        WHERE schemaname = 'public'
          AND tablename = 'promotion_canonical_change'
          AND indexname = 'ix_promotion_canonical_change__batch'
        """,
    ).scalar_one()
    assert "(promotion_batch_id, promotion_canonical_change_id)" in batch_index


def test_alias_primitives_are_exact_and_same_batch_retry_dedupes(
    database: Session,
) -> None:
    values = _base_objects(database)
    batch_id = _batch(database)
    alias_id = returning(
        database,
        """
        INSERT INTO node_alias (node_id, alias_text, language, is_preferred)
        VALUES (:node_id, :text, 'ko', false)
        RETURNING node_alias_id
        """,
        node_id=values["left"],
        text=f"stage-one-alias-{uuid4()}",
    )

    provenance.record_node_alias_changed(database, batch_id, alias_id)
    provenance.record_node_alias_changed(database, batch_id, alias_id)
    assert provenance.add_node_alias_evidence(
        database, batch_id, alias_id, values["observation"]
    )
    assert not provenance.add_node_alias_evidence(
        database, batch_id, alias_id, values["observation"]
    )

    changes = provenance.changes_for_batch(database, batch_id)
    assert [change.change_kind for change in changes] == [
        "NODE_ALIAS_CHANGED",
        "NODE_ALIAS_EVIDENCE_ADDED",
    ]


def test_claim_association_attribute_and_event_surfaces_are_exact_and_idempotent(
    database: Session,
) -> None:
    values = _base_objects(database)
    batch_id = _batch(database)

    assert provenance.add_claim_observation(
        database, batch_id, values["claim"], values["observation"]
    )
    assert not provenance.add_claim_observation(
        database, batch_id, values["claim"], values["observation"]
    )

    new_observation = _observation(database)
    assert provenance.add_claim_observation(
        database, batch_id, values["claim"], new_observation
    )

    assert provenance.add_claim_relation(
        database, batch_id, values["claim"], values["relation"], "SUPPORT"
    )
    assert not provenance.add_claim_relation(
        database, batch_id, values["claim"], values["relation"], "SUPPORT"
    )
    with pytest.raises(ValueError, match="no approved #216 change kind"):
        provenance.add_claim_relation(
            database, batch_id, values["claim"], values["relation"], "DISPUTE"
        )

    attribute_value_id = provenance.add_claim_attribute_value(
        database,
        batch_id,
        claim_id=values["claim"],
        target_node_id=values["left"],
        attribute_revision_id=values["attribute_revision"],
        value_kind="STRING",
        string_value="issue 216 value",
    )

    assert provenance.add_event_temporal_basis(
        database, batch_id, values["event"], values["claim"]
    )
    assert not provenance.add_event_temporal_basis(
        database, batch_id, values["event"], values["claim"]
    )

    changes = provenance.changes_for_batch(database, batch_id)
    assert [change.change_kind for change in changes] == [
        "CLAIM_OBSERVATION_ADDED",
        "CLAIM_OBSERVATION_ADDED",
        "CLAIM_RELATION_ADDED",
        "CLAIM_ATTRIBUTE_VALUE_ADDED",
        "EVENT_TEMPORAL_BASIS_ADDED",
    ]
    attribute_change = next(
        change
        for change in changes
        if change.change_kind == "CLAIM_ATTRIBUTE_VALUE_ADDED"
    )
    assert attribute_change.claim_attribute_value_id == attribute_value_id
    assert attribute_change.claim_id is None
    assert attribute_change.event_node_id is None


def test_canonical_mutation_and_provenance_roll_back_together(
    database: Session,
) -> None:
    values = _base_objects(database)
    observation = _observation(database)
    before_association = execute(
        database,
        """
        SELECT count(*) FROM claim_observation
        WHERE claim_id = :claim_id AND observation_id = :observation_id
        """,
        claim_id=values["claim"],
        observation_id=observation,
    ).scalar_one()

    with pytest.raises(RuntimeError, match="rollback promotion"):
        with database.begin_nested():
            batch_id = _batch(database)
            assert provenance.add_claim_observation(
                database, batch_id, values["claim"], observation
            )
            raise RuntimeError("rollback promotion")

    assert (
        execute(
            database,
            """
            SELECT count(*) FROM claim_observation
            WHERE claim_id = :claim_id AND observation_id = :observation_id
            """,
            claim_id=values["claim"],
            observation_id=observation,
        ).scalar_one()
        == before_association
    )
    assert (
        execute(
            database,
            """
            SELECT count(*) FROM promotion_canonical_change p
            JOIN promotion_batch b
              ON b.promotion_batch_id = p.promotion_batch_id
            WHERE p.claim_id = :claim_id AND p.observation_id = :observation_id
            """,
            claim_id=values["claim"],
            observation_id=observation,
        ).scalar_one()
        == 0
    )


def test_legacy_committed_not_started_batches_block_cutover_without_mutation(
    database: Session,
) -> None:
    assert provenance.legacy_committed_not_started_batch_ids(database) == ()
    provenance.assert_initial_publication_cutover_safe(database)

    legacy_batch = _batch(database, committed=True)
    before = execute(
        database,
        """
        SELECT promotion_status, publication_status
        FROM promotion_batch WHERE promotion_batch_id = :batch
        """,
        batch=legacy_batch,
    ).one()
    assert legacy_batch in provenance.legacy_committed_not_started_batch_ids(database)
    with pytest.raises(RuntimeError, match="cutover is blocked"):
        provenance.assert_initial_publication_cutover_safe(database)
    after = execute(
        database,
        """
        SELECT promotion_status, publication_status
        FROM promotion_batch WHERE promotion_batch_id = :batch
        """,
        batch=legacy_batch,
    ).one()
    assert after == before


def test_concurrent_claim_observation_insert_attributes_only_the_winner() -> None:
    engine = sa.create_engine(_checked_url())
    token = uuid4().hex
    with Session(engine) as setup, setup.begin():
        base_batch = _batch(setup, ready=True)
        claim_id = _claim(setup, base_batch, f"concurrent {token}")
        observation_id = _observation(setup, f"concurrent evidence {token}")
        first_batch = _batch(setup)
        second_batch = _batch(setup)

    barrier = Barrier(2)

    def worker(batch_id: int) -> tuple[int, bool]:
        with Session(engine) as session, session.begin():
            barrier.wait()
            inserted = provenance.add_claim_observation(
                session, batch_id, claim_id, observation_id
            )
            execute(
                session,
                """
                UPDATE promotion_batch
                SET promotion_status = 'COMMITTED', committed_at = CURRENT_TIMESTAMP
                WHERE promotion_batch_id = :batch
                """,
                batch=batch_id,
            )
            return batch_id, inserted

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(worker, (first_batch, second_batch)))

    winners = [batch_id for batch_id, inserted in results if inserted]
    assert len(winners) == 1
    with Session(engine) as verify, verify.begin():
        rows = (
            execute(
                verify,
                """
            SELECT promotion_batch_id
            FROM promotion_canonical_change
            WHERE change_kind = 'CLAIM_OBSERVATION_ADDED'
              AND claim_id = :claim_id
              AND observation_id = :observation_id
            """,
                claim_id=claim_id,
                observation_id=observation_id,
            )
            .scalars()
            .all()
        )
        assert rows == winners
        execute(
            verify,
            """
            UPDATE promotion_batch
            SET publication_status = 'READY', ready_at = CURRENT_TIMESTAMP
            WHERE promotion_batch_id IN (:first_batch, :second_batch)
            """,
            first_batch=first_batch,
            second_batch=second_batch,
        )
    engine.dispose()
