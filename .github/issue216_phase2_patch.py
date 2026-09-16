from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one replacement anchor, found {count}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_between(path: str, start: str, end: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    start_pos = text.index(start)
    end_pos = text.index(end, start_pos)
    file.write_text(text[:start_pos] + new + text[end_pos:], encoding="utf-8")


# Wire the actual merged #128 promotion path. Alias insertion winner and alias
# evidence association winner are now attributed in the same caller transaction.
path = "server/src/ontology_map/db/entity_resolution.py"
replace_once(
    path,
    "from sqlalchemy.orm import Session\n\nfrom ontology_map.entity_resolution_contracts import (",
    "from sqlalchemy.orm import Session\n\nfrom ontology_map.db import promotion_provenance as provenance\nfrom ontology_map.entity_resolution_contracts import (",
)
new_alias = '''def _ensure_alias(
    session: Session,
    batch_id: int,
    node_id: int,
    text: str,
    language: str,
    observation_id: int,
    *,
    preferred: bool,
) -> None:
    """Apply alias canonical changes and #216 provenance in one transaction."""
    values = {
        "node_id": node_id,
        "text": text,
        "language": language,
        "preferred": preferred,
        "observation_id": observation_id,
    }
    existing = session.execute(
        _ids_statement(
            _FAMILY
            + """
        SELECT a.node_alias_id FROM family f
        JOIN node_alias a ON a.node_id = f.member_id
        WHERE a.alias_text = :text
        ORDER BY (a.node_id = :node_id) DESC,
                 (a.language = :language) DESC, a.node_alias_id
        LIMIT 1
    """
        ),
        {**values, "ids": [node_id]},
    ).scalar_one_or_none()
    if existing is None:
        inserted = session.execute(
            sa.text("""
            INSERT INTO node_alias (node_id, alias_text, language, is_preferred)
            VALUES (:node_id, :text, :language, :preferred)
            ON CONFLICT (node_id, alias_text, language) DO NOTHING
            RETURNING node_alias_id
        """),
            values,
        ).scalar_one_or_none()
        if inserted is not None:
            existing = int(inserted)
            provenance.record_node_alias_changed(session, batch_id, existing)
        else:
            existing = session.execute(
                sa.text("""
                SELECT node_alias_id FROM node_alias
                WHERE node_id = :node_id AND alias_text = :text
                  AND language = :language
            """),
                values,
            ).scalar_one()
    provenance.add_node_alias_evidence(
        session,
        batch_id,
        int(existing),
        observation_id,
    )


'''
replace_between(path, "def _ensure_alias(\n", "def has_evidenced_usage(\n", new_alias)

path = "server/src/ontology_map/entity_resolution.py"
replace_once(
    path,
    "            queries._ensure_alias(\n                session,\n                node_id,",
    "            queries._ensure_alias(\n                session,\n                batch_id,\n                node_id,",
)
replace_once(
    path,
    "    The owner marks COMMITTED only after this context exits successfully.\n",
    "    The owner marks COMMITTED only after this context exits successfully;\n"
    "    #216 exposes promotion_provenance.mark_promotion_committed for that boundary.\n",
)

# Make the provenance-aware canonical service safe for exact attribute-value
# replay. A claim row lock serializes exact-value check+insert between promotion
# transactions without inventing a new semantic UNIQUE constraint.
path = "server/src/ontology_map/db/promotion_provenance.py"
new_attribute = '''def add_claim_attribute_value(
    session: Session,
    batch_id: int,
    *,
    claim_id: int,
    target_node_id: int,
    attribute_revision_id: int,
    value_kind: str,
    string_value: str | None = None,
    number_value: Decimal | int | None = None,
    unit_code: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    date_from_precision: str = "UNKNOWN",
    date_to_precision: str = "UNKNOWN",
    boolean_value: bool | None = None,
) -> int:
    """Reuse an exact stored value or insert it with immutable provenance.

    The schema intentionally has no semantic-value UNIQUE constraint. Locking the
    owning Claim makes the exact stored tuple check deterministic for callers of
    this production write boundary, including concurrent retry transactions.
    """
    require_pending_batch(session, batch_id)
    values = {
        "claim_id": claim_id,
        "target_node_id": target_node_id,
        "attribute_revision_id": attribute_revision_id,
        "value_kind": value_kind,
        "string_value": string_value,
        "number_value": number_value,
        "unit_code": unit_code,
        "date_from": date_from,
        "date_to": date_to,
        "date_from_precision": date_from_precision,
        "date_to_precision": date_to_precision,
        "boolean_value": boolean_value,
    }
    session.execute(
        sa.text("SELECT claim_id FROM claim WHERE claim_id = :claim_id FOR UPDATE"),
        {"claim_id": claim_id},
    ).scalar_one()
    existing = session.execute(
        sa.text("""
            SELECT claim_attribute_value_id
            FROM claim_attribute_value
            WHERE claim_id = :claim_id
              AND target_node_id = :target_node_id
              AND attribute_revision_id = :attribute_revision_id
              AND value_kind = :value_kind
              AND string_value IS NOT DISTINCT FROM :string_value
              AND number_value IS NOT DISTINCT FROM :number_value
              AND unit_code IS NOT DISTINCT FROM :unit_code
              AND date_from IS NOT DISTINCT FROM :date_from
              AND date_to IS NOT DISTINCT FROM :date_to
              AND date_from_precision = :date_from_precision
              AND date_to_precision = :date_to_precision
              AND boolean_value IS NOT DISTINCT FROM :boolean_value
            ORDER BY claim_attribute_value_id
            LIMIT 1
        """),
        values,
    ).scalar_one_or_none()
    if existing is not None:
        return int(existing)
    value_id = int(
        session.execute(
            sa.text("""
                INSERT INTO claim_attribute_value (
                    claim_id, target_node_id, attribute_revision_id, value_kind,
                    string_value, number_value, unit_code, date_from, date_to,
                    date_from_precision, date_to_precision, boolean_value
                ) VALUES (
                    :claim_id, :target_node_id, :attribute_revision_id, :value_kind,
                    :string_value, :number_value, :unit_code, :date_from, :date_to,
                    :date_from_precision, :date_to_precision, :boolean_value
                )
                RETURNING claim_attribute_value_id
            """),
            values,
        ).scalar_one()
    )
    _record_change(
        session,
        batch_id,
        "CLAIM_ATTRIBUTE_VALUE_ADDED",
        claim_attribute_value_id=value_id,
    )
    return value_id


'''
replace_between(
    path,
    "def add_claim_attribute_value(\n",
    "def add_event_temporal_basis(\n",
    new_attribute,
)
commit_boundary = '''def mark_promotion_committed(session: Session, batch_id: int) -> None:
    """Finish the caller-owned promotion transaction without committing it."""
    require_pending_batch(session, batch_id)
    session.execute(
        sa.text("""
            UPDATE promotion_batch
            SET promotion_status = 'COMMITTED', committed_at = CURRENT_TIMESTAMP
            WHERE promotion_batch_id = :batch_id
            RETURNING promotion_batch_id
        """),
        {"batch_id": batch_id},
    ).scalar_one()


'''
file = Path(path)
text = file.read_text(encoding="utf-8")
anchor = "def changes_for_batch(\n"
if commit_boundary not in text:
    pos = text.index(anchor)
    text = text[:pos] + commit_boundary + text[pos:]
    file.write_text(text, encoding="utf-8")

# Phase-two PostgreSQL regressions. Keep projection SQL in tests: #216 proves
# that persisted facts are sufficient, while #215 owns the coordinator itself.
path = "server/tests/test_promotion_provenance_postgres.py"
replace_once(
    path,
    "from ontology_map.db import promotion_provenance as provenance\n",
    "from ontology_map.db import entity_resolution as entity_db\n"
    "from ontology_map.db import promotion_provenance as provenance\n",
)
file = Path(path)
text = file.read_text(encoding="utf-8")
helper_anchor = "def _checked_url() -> sa.URL:\n"
projection_helper = '''def _direct_affected_nodes(session: Session, batch_id: int) -> set[int]:
    """Read-only #215 projection oracle over the two approved provenance sources."""
    return set(
        int(value)
        for value in execute(
            session,
            """
            WITH batch_items AS (
                SELECT knowledge_item_id, item_kind
                FROM knowledge_item
                WHERE promotion_batch_id = :batch_id
            ), projection_claims AS (
                SELECT knowledge_item_id AS claim_id
                FROM batch_items WHERE item_kind = 'CLAIM'
                UNION
                SELECT claim_id FROM promotion_canonical_change
                WHERE promotion_batch_id = :batch_id
                  AND change_kind = 'CLAIM_OBSERVATION_ADDED'
            ), affected(node_id) AS (
                SELECT n.node_id
                FROM batch_items b JOIN node n ON n.node_id = b.knowledge_item_id
                WHERE b.item_kind = 'NODE'
                UNION
                SELECT r.source_node_id
                FROM batch_items b JOIN relation r
                  ON r.relation_id = b.knowledge_item_id
                WHERE b.item_kind = 'RELATION'
                UNION
                SELECT r.target_node_id
                FROM batch_items b JOIN relation r
                  ON r.relation_id = b.knowledge_item_id
                WHERE b.item_kind = 'RELATION'
                UNION
                SELECT a.node_id
                FROM promotion_canonical_change p
                JOIN node_alias a ON a.node_alias_id = p.node_alias_id
                WHERE p.promotion_batch_id = :batch_id
                  AND p.change_kind IN (
                    'NODE_ALIAS_CHANGED', 'NODE_ALIAS_EVIDENCE_ADDED'
                  )
                UNION
                SELECT r.source_node_id
                FROM promotion_canonical_change p
                JOIN relation r ON r.relation_id = p.relation_id
                WHERE p.promotion_batch_id = :batch_id
                  AND p.change_kind = 'CLAIM_RELATION_ADDED'
                UNION
                SELECT r.target_node_id
                FROM promotion_canonical_change p
                JOIN relation r ON r.relation_id = p.relation_id
                WHERE p.promotion_batch_id = :batch_id
                  AND p.change_kind = 'CLAIM_RELATION_ADDED'
                UNION
                SELECT v.target_node_id
                FROM promotion_canonical_change p
                JOIN claim_attribute_value v
                  ON v.claim_attribute_value_id = p.claim_attribute_value_id
                WHERE p.promotion_batch_id = :batch_id
                  AND p.change_kind = 'CLAIM_ATTRIBUTE_VALUE_ADDED'
                UNION
                SELECT p.event_node_id
                FROM promotion_canonical_change p
                WHERE p.promotion_batch_id = :batch_id
                  AND p.change_kind = 'EVENT_TEMPORAL_BASIS_ADDED'
                UNION
                SELECT r.source_node_id
                FROM projection_claims c
                JOIN claim_relation cr ON cr.claim_id = c.claim_id
                JOIN relation r ON r.relation_id = cr.relation_id
                UNION
                SELECT r.target_node_id
                FROM projection_claims c
                JOIN claim_relation cr ON cr.claim_id = c.claim_id
                JOIN relation r ON r.relation_id = cr.relation_id
                UNION
                SELECT v.target_node_id
                FROM projection_claims c
                JOIN claim_attribute_value v ON v.claim_id = c.claim_id
                UNION
                SELECT e.event_node_id
                FROM projection_claims c
                JOIN event_temporal_basis e ON e.claim_id = c.claim_id
            )
            SELECT node_id FROM affected WHERE node_id IS NOT NULL ORDER BY node_id
            """,
            batch_id=batch_id,
        ).scalars()
    )


'''
if projection_helper not in text:
    pos = text.index(helper_anchor)
    text = text[:pos] + projection_helper + text[pos:]
    file.write_text(text, encoding="utf-8")

# Use the real merged #128 alias write primitive in the focused provenance test.
file = Path(path)
text = file.read_text(encoding="utf-8")
start = text.index("def test_alias_primitives_are_exact_and_same_batch_retry_dedupes(")
end = text.index("def test_claim_association_attribute_and_event_surfaces_are_exact_and_idempotent(", start)
alias_test = '''def test_alias_production_primitive_tracks_only_actual_mutations(
    database: Session,
) -> None:
    values = _base_objects(database)
    batch_id = _batch(database)
    alias_text = f"phase-two-alias-{uuid4()}"

    entity_db._ensure_alias(
        database,
        batch_id,
        values["left"],
        alias_text,
        "ko",
        values["observation"],
        preferred=False,
    )
    entity_db._ensure_alias(
        database,
        batch_id,
        values["left"],
        alias_text,
        "ko",
        values["observation"],
        preferred=False,
    )
    second_observation = _observation(database, "second alias evidence")
    entity_db._ensure_alias(
        database,
        batch_id,
        values["left"],
        alias_text,
        "ko",
        second_observation,
        preferred=False,
    )

    changes = provenance.changes_for_batch(database, batch_id)
    assert [change.change_kind for change in changes] == [
        "NODE_ALIAS_CHANGED",
        "NODE_ALIAS_EVIDENCE_ADDED",
        "NODE_ALIAS_EVIDENCE_ADDED",
    ]


'''
text = text[:start] + alias_test + text[end:]
file.write_text(text, encoding="utf-8")

# Exact attribute retry reuses the same physical value and creates no duplicate provenance.
replace_once(
    path,
    '''    attribute_value_id = provenance.add_claim_attribute_value(
        database,
        batch_id,
        claim_id=values["claim"],
        target_node_id=values["left"],
        attribute_revision_id=values["attribute_revision"],
        value_kind="STRING",
        string_value="issue 216 value",
    )

    assert provenance.add_event_temporal_basis(''',
    '''    attribute_value_id = provenance.add_claim_attribute_value(
        database,
        batch_id,
        claim_id=values["claim"],
        target_node_id=values["left"],
        attribute_revision_id=values["attribute_revision"],
        value_kind="STRING",
        string_value="issue 216 value",
    )
    retry_attribute_value_id = provenance.add_claim_attribute_value(
        database,
        batch_id,
        claim_id=values["claim"],
        target_node_id=values["left"],
        attribute_revision_id=values["attribute_revision"],
        value_kind="STRING",
        string_value="issue 216 value",
    )
    assert retry_attribute_value_id == attribute_value_id

    assert provenance.add_event_temporal_basis(''',
)
replace_once(
    path,
    '''            execute(
                session,
                """
                UPDATE promotion_batch
                SET promotion_status = 'COMMITTED', committed_at = CURRENT_TIMESTAMP
                WHERE promotion_batch_id = :batch
                """,
                batch=batch_id,
            )
            return batch_id, inserted
''',
    '''            provenance.mark_promotion_committed(session, batch_id)
            return batch_id, inserted
''',
)

extra_tests = r'''


def test_all_six_mutation_kinds_roll_back_together(database: Session) -> None:
    values = _base_objects(database)
    batch_id = _batch(database)
    alias_text = f"rollback-alias-{uuid4()}"

    with pytest.raises(RuntimeError, match="rollback all six"):
        with database.begin_nested():
            entity_db._ensure_alias(
                database,
                batch_id,
                values["left"],
                alias_text,
                "ko",
                values["observation"],
                preferred=False,
            )
            assert provenance.add_claim_observation(
                database, batch_id, values["claim"], values["observation"]
            )
            assert provenance.add_claim_relation(
                database, batch_id, values["claim"], values["relation"], "SUPPORT"
            )
            provenance.add_claim_attribute_value(
                database,
                batch_id,
                claim_id=values["claim"],
                target_node_id=values["left"],
                attribute_revision_id=values["attribute_revision"],
                value_kind="STRING",
                string_value="rollback value",
            )
            assert provenance.add_event_temporal_basis(
                database, batch_id, values["event"], values["claim"]
            )
            raise RuntimeError("rollback all six")

    assert provenance.changes_for_batch(database, batch_id) == ()
    assert (
        execute(
            database,
            "SELECT count(*) FROM node_alias WHERE alias_text = :text",
            text=alias_text,
        ).scalar_one()
        == 0
    )
    assert (
        execute(
            database,
            """
            SELECT count(*) FROM claim_observation
            WHERE claim_id = :claim AND observation_id = :observation
            """,
            claim=values["claim"],
            observation=values["observation"],
        ).scalar_one()
        == 0
    )
    assert (
        execute(
            database,
            "SELECT count(*) FROM claim_relation WHERE claim_id = :claim",
            claim=values["claim"],
        ).scalar_one()
        == 0
    )
    assert (
        execute(
            database,
            "SELECT count(*) FROM claim_attribute_value WHERE claim_id = :claim",
            claim=values["claim"],
        ).scalar_one()
        == 0
    )
    assert (
        execute(
            database,
            "SELECT count(*) FROM event_temporal_basis WHERE claim_id = :claim",
            claim=values["claim"],
        ).scalar_one()
        == 0
    )


def test_provenance_failure_rolls_back_canonical_mutation(
    database: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values = _base_objects(database)
    observation = _observation(database, "injected provenance failure")
    batch_id = _batch(database)

    def fail_record(*args: object, **kwargs: object) -> None:
        raise RuntimeError("synthetic provenance failure")

    monkeypatch.setattr(provenance, "_record_change", fail_record)
    with pytest.raises(RuntimeError, match="synthetic provenance failure"):
        with database.begin_nested():
            provenance.add_claim_observation(
                database, batch_id, values["claim"], observation
            )
    assert (
        execute(
            database,
            """
            SELECT count(*) FROM claim_observation
            WHERE claim_id = :claim AND observation_id = :observation
            """,
            claim=values["claim"],
            observation=observation,
        ).scalar_one()
        == 0
    )


def test_publication_lifecycle_never_consumes_provenance(database: Session) -> None:
    values = _base_objects(database)
    batch_id = _batch(database)
    assert provenance.add_claim_observation(
        database, batch_id, values["claim"], values["observation"]
    )
    provenance.mark_promotion_committed(database, batch_id)
    ids = tuple(
        change.promotion_canonical_change_id
        for change in provenance.changes_for_batch(database, batch_id)
    )
    updates = (
        """
        UPDATE promotion_batch SET publication_status = 'PREPARING'
        WHERE promotion_batch_id = :batch
        """,
        """
        UPDATE promotion_batch
        SET publication_status = 'FAILED',
            publication_failure_reason = 'synthetic publication failure'
        WHERE promotion_batch_id = :batch
        """,
        """
        UPDATE promotion_batch
        SET publication_status = 'PREPARING', publication_failure_reason = NULL
        WHERE promotion_batch_id = :batch
        """,
        """
        UPDATE promotion_batch
        SET publication_status = 'READY', ready_at = CURRENT_TIMESTAMP
        WHERE promotion_batch_id = :batch
        """,
    )
    for sql in updates:
        execute(database, sql, batch=batch_id)
        assert tuple(
            change.promotion_canonical_change_id
            for change in provenance.changes_for_batch(database, batch_id)
        ) == ids


def test_restart_reconstructs_sources_and_direct_projection_without_two_hop() -> None:
    engine = sa.create_engine(_checked_url())
    try:
        with Session(engine) as writer, writer.begin():
            values = _base_objects(writer)
            unrelated_relation = _relation(
                writer,
                values["base_batch"],
                values["right"],
                values["third"],
            )
            assert unrelated_relation
            attribute_target = _node(writer, values["base_batch"])
            batch_id = _batch(writer)

            new_node = _node(writer, batch_id)
            new_relation = _relation(writer, batch_id, new_node, values["left"])
            new_claim = _claim(writer, batch_id, "new multi-target claim")
            execute(
                writer,
                """
                INSERT INTO claim_relation (claim_id, relation_id, stance)
                VALUES (:claim, :relation, 'SUPPORT')
                """,
                claim=new_claim,
                relation=new_relation,
            )
            execute(
                writer,
                """
                INSERT INTO claim_attribute_value (
                    claim_id, target_node_id, attribute_revision_id, value_kind,
                    string_value, date_from_precision, date_to_precision
                ) VALUES (
                    :claim, :target, :revision, 'STRING',
                    'new claim value', 'UNKNOWN', 'UNKNOWN'
                )
                """,
                claim=new_claim,
                target=attribute_target,
                revision=values["attribute_revision"],
            )
            execute(
                writer,
                """
                INSERT INTO event_temporal_basis (event_node_id, claim_id)
                VALUES (:event, :claim)
                """,
                event=values["event"],
                claim=new_claim,
            )

            alias_observation = _observation(writer, "phase two alias evidence")
            alias_text = f"restart-alias-{uuid4()}"
            entity_db._ensure_alias(
                writer,
                batch_id,
                values["left"],
                alias_text,
                "ko",
                alias_observation,
                preferred=False,
            )
            second_alias_observation = _observation(
                writer, "phase two second alias evidence"
            )
            entity_db._ensure_alias(
                writer,
                batch_id,
                values["left"],
                alias_text,
                "ko",
                second_alias_observation,
                preferred=False,
            )

            added_observation = _observation(writer, "existing claim new evidence")
            assert provenance.add_claim_observation(
                writer, batch_id, values["claim"], added_observation
            )
            assert provenance.add_claim_relation(
                writer, batch_id, values["claim"], values["relation"], "SUPPORT"
            )
            provenance.add_claim_attribute_value(
                writer,
                batch_id,
                claim_id=values["claim"],
                target_node_id=attribute_target,
                attribute_revision_id=values["attribute_revision"],
                value_kind="STRING",
                string_value="existing claim new value",
            )
            assert provenance.add_event_temporal_basis(
                writer, batch_id, values["event"], values["claim"]
            )
            provenance.mark_promotion_committed(writer, batch_id)

        with Session(engine) as restarted:
            item_kinds = set(
                execute(
                    restarted,
                    """
                    SELECT item_kind FROM knowledge_item
                    WHERE promotion_batch_id = :batch
                    """,
                    batch=batch_id,
                ).scalars()
            )
            assert item_kinds == {"NODE", "RELATION", "CLAIM"}
            changes = provenance.changes_for_batch(restarted, batch_id)
            assert {change.change_kind for change in changes} == set(
                provenance.CHANGE_KINDS
            )
            assert _direct_affected_nodes(restarted, batch_id) == {
                new_node,
                values["left"],
                values["right"],
                attribute_target,
                values["event"],
            }
            assert values["third"] not in _direct_affected_nodes(restarted, batch_id)
            assert (
                execute(
                    restarted,
                    """
                    SELECT count(*) FROM publication_affected_node
                    WHERE promotion_batch_id = :batch
                    """,
                    batch=batch_id,
                ).scalar_one()
                == 0
            )
            assert execute(
                restarted,
                """
                SELECT promotion_status, publication_status
                FROM promotion_batch WHERE promotion_batch_id = :batch
                """,
                batch=batch_id,
            ).one() == ("COMMITTED", "NOT_STARTED")

        with Session(engine) as cleanup, cleanup.begin():
            execute(
                cleanup,
                """
                UPDATE promotion_batch
                SET publication_status = 'READY', ready_at = CURRENT_TIMESTAMP
                WHERE promotion_batch_id = :batch
                """,
                batch=batch_id,
            )
    finally:
        engine.dispose()
'''
file = Path(path)
text = file.read_text(encoding="utf-8")
if "def test_all_six_mutation_kinds_roll_back_together" not in text:
    file.write_text(text.rstrip() + extra_tests + "\n", encoding="utf-8")

# Existing Entity Resolution application service must prove real alias wiring,
# not just the lower-level provenance module.
path = "server/tests/test_entity_resolution_postgres.py"
replace_once(
    path,
    "from ontology_map.db import entity_resolution as db\n",
    "from ontology_map.db import entity_resolution as db\n"
    "from ontology_map.db import promotion_provenance as provenance\n",
)
replace_once(
    path,
    '''    assert (
        execute(
            database,
            """
        SELECT promotion_batch_id FROM knowledge_item
        WHERE knowledge_item_id = :node_id
    """,
            node_id=saved_id,
        ).scalar_one()
        == promotion_id
    )
''',
    '''    changes = provenance.changes_for_batch(database, promotion_id)
    assert [change.change_kind for change in changes] == [
        "NODE_ALIAS_CHANGED",
        "NODE_ALIAS_EVIDENCE_ADDED",
    ]
    assert (
        execute(
            database,
            """
        SELECT promotion_batch_id FROM knowledge_item
        WHERE knowledge_item_id = :node_id
    """,
            node_id=saved_id,
        ).scalar_one()
        == promotion_id
    )
''',
)
existing_alias_test = r'''


def test_existing_alias_reuse_records_only_new_evidence(database):
    name = f"Existing{uuid4().hex}"
    canonical = node(database, name)
    target = source_mention(database, name)
    result = service.resolve_mention(database, target, propose("SAME", canonical))
    assert (result.decision, result.node_id) == ("SAME", canonical)
    promotion_id = batch(database)

    with service.resolved_nodes_for_promotion(
        database, promotion_id, (result,), frozenset({"m1"})
    ):
        pass
    first = provenance.changes_for_batch(database, promotion_id)
    assert [change.change_kind for change in first] == ["NODE_ALIAS_EVIDENCE_ADDED"]

    with service.resolved_nodes_for_promotion(
        database, promotion_id, (result,), frozenset({"m1"})
    ):
        pass
    assert provenance.changes_for_batch(database, promotion_id) == first
'''
file = Path(path)
text = file.read_text(encoding="utf-8")
anchor = "\n\n@pytest.mark.parametrize(\"failure\", [\"orphan\", \"writer\"])"
if "def test_existing_alias_reuse_records_only_new_evidence" not in text:
    pos = text.index(anchor)
    text = text[:pos] + existing_alias_test + text[pos:]
    file.write_text(text, encoding="utf-8")

# Canonical docs own long-lived schema facts. Remove the phase-1 handoff note
# instead of keeping a fourth manually duplicated schema source.
phase1_note = Path("docs/data/promotion-canonical-provenance.md")
if phase1_note.exists():
    phase1_note.unlink()

replace_once(
    "docs/data/physical-schema.md",
    "#216 1/2, `server/migrations/versions/0005_add_promotion_canonical_change.py`",
    "#216, `server/migrations/versions/0005_add_promotion_canonical_change.py`",
)
replace_once(
    "docs/data/physical-schema.md",
    "migration `0005`는 historical association을 backfill하지 않는다. transaction-local primitive는 caller가 연 promotion transaction 안에서만 동작하고 association insert는 `INSERT ... ON CONFLICT DO NOTHING RETURNING ...` 결과로 실제 mutation 여부를 판별할 수 있게 한다. 이번 #216 1/2 단계는 이 persistence/primitive/guard까지 구현하며 repository 전체 production promotion writer의 최종 6종 wiring은 2/2 단계에 남긴다.",
    "migration `0005`는 historical association을 backfill하지 않는다. `ontology_map.db.promotion_provenance`의 production write boundary는 caller가 연 promotion transaction 안에서만 동작하고 association insert는 `INSERT ... ON CONFLICT DO NOTHING RETURNING ...` 결과로 실제 mutation 여부를 판별한다. `claim_attribute_value` exact retry는 owning Claim row를 잠근 뒤 exact stored tuple을 재조회해 기존 행을 재사용한다. merged #128 Entity Resolution의 alias/alias-evidence path는 이 boundary에 직접 연결되어 실제 INSERT winner만 provenance를 남긴다. Claim/Relation/attribute/event canonical service도 같은 transaction-local boundary를 제공하며, 최종 KNOWLEDGE_EXTRACTION orchestration은 별도 #127 책임이다. `mark_promotion_committed`는 canonical writes와 provenance 뒤 같은 caller transaction에서 `COMMITTED`를 확정하지만 commit 자체는 호출하지 않는다. #215 initial publication coordinator와 #180 recovery는 별도 책임으로 남는다.",
)

replace_once(
    "docs/operations/database.md",
    "현재 기준 revision은 `0001_create_frozen_schema.py` → `0002_add_panel_reading_contracts.py` → `0003_support_multiple_number_attribute_units.py` → `0004_support_topic_reference_lifecycle.py`다.",
    "현재 기준 revision은 `0001_create_frozen_schema.py` → `0002_add_panel_reading_contracts.py` → `0003_support_multiple_number_attribute_units.py` → `0004_support_topic_reference_lifecycle.py` → `0005_add_promotion_canonical_change.py`다.",
)
replace_once(
    "docs/operations/database.md",
    "`0004` 자체는 제품 Topic row를 seed하지 않고 startup도 누락 Topic을 자동 생성하지 않는다. 승인 Topic 9개의 실제 활성화는 migration과 분리된 #201 명시적 reference activation transaction이 담당한다. 개발 fixture의 evidence-backed TOPIC과 제품 Reference Topic을 같은 데이터로 간주하지 않는다.\n",
    "`0004` 자체는 제품 Topic row를 seed하지 않고 startup도 누락 Topic을 자동 생성하지 않는다. 승인 Topic 9개의 실제 활성화는 migration과 분리된 #201 명시적 reference activation transaction이 담당한다. 개발 fixture의 evidence-backed TOPIC과 제품 Reference Topic을 같은 데이터로 간주하지 않는다.\n\n`0005`는 #216의 immutable `promotion_canonical_change` provenance만 추가하며 historical association을 추정 backfill하지 않는다. initial publication coordinator를 enable하기 전 `COMMITTED + NOT_STARTED` legacy batch가 있으면 `assert_initial_publication_cutover_safe()`가 차단하며 timestamp attribution, 자동 skip, provenance fabrication이나 publication 상태 변경을 수행하지 않는다. 실제 one-time remediation은 별도 운영 판단 없이 이 migration이 자동 수행하지 않는다.\n",
)

# ADR-0006 records the implemented promotion-side boundary without claiming
# that #215 publication orchestration or #180 recovery is complete.
replace_once(
    "docs/architecture/decisions/current/0006-separate-promotion-and-publication.md",
    "evidence: [#23](https://github.com/studylida/ontology-map/issues/23), [#46](https://github.com/studylida/ontology-map/issues/46), [PR #77](https://github.com/studylida/ontology-map/pull/77), [#95](https://github.com/studylida/ontology-map/issues/95), [PR #101](https://github.com/studylida/ontology-map/pull/101), [#121](https://github.com/studylida/ontology-map/issues/121), [ADR-0008](0008-remove-node-embedding-pgvector.md)",
    "evidence: [#23](https://github.com/studylida/ontology-map/issues/23), [#46](https://github.com/studylida/ontology-map/issues/46), [PR #77](https://github.com/studylida/ontology-map/pull/77), [#95](https://github.com/studylida/ontology-map/issues/95), [PR #101](https://github.com/studylida/ontology-map/pull/101), [#121](https://github.com/studylida/ontology-map/issues/121), [#216](https://github.com/studylida/ontology-map/issues/216), [ADR-0008](0008-remove-node-embedding-pgvector.md)",
)
replace_once(
    "docs/architecture/decisions/current/0006-separate-promotion-and-publication.md",
    "`promotion_status`와 `publication_status`를 독립된 수명주기로 둔다. promotion은 기준 지식 저장의 원자 성공이나 실패를 나타내고, publication은 그 결과에 필요한 파생 산출물이 완결됐는지 나타낸다. 새 publication이 실패해도 저장된 기준 지식과 이전 `READY` 결과를 보존하며, 일반 조회는 최신 `COMMITTED + READY` 결과를 선택한다.\n",
    "`promotion_status`와 `publication_status`를 독립된 수명주기로 둔다. promotion은 기준 지식 저장의 원자 성공이나 실패를 나타내고, publication은 그 결과에 필요한 파생 산출물이 완결됐는지 나타낸다. 새 publication이 실패해도 저장된 기준 지식과 이전 `READY` 결과를 보존하며, 일반 조회는 최신 `COMMITTED + READY` 결과를 선택한다. #216은 기존 canonical association/change의 batch attribution이 필요한 경우 `promotion_canonical_change`를 canonical mutation과 같은 promotion transaction에서 기록하고 `COMMITTED`까지만 확정한다. affected Node projection과 `PREPARING` 진입은 계속 별도 #215 coordinator 책임이다.\n",
)
replace_once(
    "docs/architecture/decisions/current/0006-separate-promotion-and-publication.md",
    "기준 지식 저장과 파생 결과 준비를 독립적으로 재시도하고 이전 공개 결과를 계속 제공할 수 있다. 대신 여러 table의 완결성을 application service transaction에서 검사해야 한다. 현재 schema와 읽기 경로는 이 계약을 표현하지만 promotion·publication worker는 아직 구현되지 않았다.",
    "기준 지식 저장과 파생 결과 준비를 독립적으로 재시도하고 이전 공개 결과를 계속 제공할 수 있다. 대신 여러 table의 완결성을 application service transaction에서 검사해야 한다. #216의 promotion-side canonical-change provenance와 transaction-local write/COMMITTED boundary는 구현되어 있으며 merged #128 alias 경로가 이를 사용한다. 전체 KNOWLEDGE_EXTRACTION orchestration은 #127, initial publication coordinator는 #215, READY 무효화 recovery는 #180이 각각 소유하므로 이 ADR은 그 worker들이 모두 구현됐다고 주장하지 않는다.",
)

print("issue #216 phase-two patch applied")
