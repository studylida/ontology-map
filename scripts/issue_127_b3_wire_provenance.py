from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROMOTION = ROOT / "server/src/ontology_map/extraction_promotion.py"
DB_PROMOTION = ROOT / "server/src/ontology_map/db/extraction_promotion.py"
TEST = ROOT / "server/tests/test_extraction_promotion_postgres.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"{label}: expected one anchor, got {text.count(old)}")
    return text.replace(old, new, 1)


def replace_regex(text: str, pattern: str, replacement: str, label: str) -> str:
    changed, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"{label}: expected one regex match, got {count}")
    return changed


# ---- product finalizer ----------------------------------------------------
text = PROMOTION.read_text()
text = replace_once(
    text,
    '''"""B-3 product finalization for KNOWLEDGE_EXTRACTION (#127).\n\nRuntime extraction and #128 resolution stay in memory.  Only the final short\npromotion transaction writes canonical knowledge and the model_task terminal\nstate.  #216 provenance is intentionally not reimplemented here: if an\nexisting canonical object would need new durable attribution while #216 is not\non main, finalization returns DEPENDENCY_BLOCKED_216 before that mutation.\n"""''',
    '''"""B-3 product finalization for KNOWLEDGE_EXTRACTION (#127).\n\nRuntime extraction and #128 resolution stay in memory. Only the final short\ncaller-owned promotion transaction writes canonical knowledge, records the\nofficial #216 provenance for canonical associations, marks the promotion\nCOMMITTED, and finishes the model_task. Provider/model IO never runs here.\n"""''',
    "module docstring",
)
text = replace_once(
    text,
    "from typing import Callable, Literal, Mapping, Sequence",
    "from typing import Any, Callable, Literal, Mapping, Sequence",
    "typing import",
)
text = replace_once(
    text,
    "from ontology_map.db import extraction_promotion as promotion_db\nfrom ontology_map.db import extraction_tasks as inputs",
    "from ontology_map.db import extraction_promotion as promotion_db\nfrom ontology_map.db import extraction_tasks as inputs\nfrom ontology_map.db import promotion_provenance as provenance",
    "official provenance import",
)
text = replace_once(
    text,
    '''ProductDisposition = Literal[\n    "SUCCESS",\n    "VALIDATION_BLOCKED",\n    "DEPENDENCY_BLOCKED_216",\n    "RETRY_WAIT",\n    "FINAL_FAILED",\n    "LEASE_LOST",\n]\n\n\nclass DependencyBlocked216(RuntimeError):\n    """A real existing-canonical mutation needs #216 provenance first."""\n''',
    '''ProductDisposition = Literal[\n    "SUCCESS",\n    "VALIDATION_BLOCKED",\n    "RETRY_WAIT",\n    "FINAL_FAILED",\n    "LEASE_LOST",\n]\n''',
    "stale #216 disposition",
)
text = replace_regex(
    text,
    r"\n\ndef _assert_same_alias_noop\(.*?\n\ndef _attribute_values\(",
    "\n\ndef _attribute_values(",
    "stale alias guard",
)
text = text.replace("def _attribute_values(\n", "def _attribute_values(\n", 1)
text = replace_once(
    text,
    ") -> dict[str, object]:\n    value = proposal.value\n    result: dict[str, object] = {",
    ") -> dict[str, Any]:\n    value = proposal.value\n    result: dict[str, Any] = {",
    "attribute value typing",
)
text = replace_once(
    text,
    '''class _ClaimBindings:\n    relations: tuple[tuple[int, str], ...]\n    attributes: tuple[Mapping[str, object], ...]\n    events: tuple[_ResolvedEvent, ...]''',
    '''class _ClaimBindings:\n    relations: tuple[tuple[int, str], ...]\n    attributes: tuple[dict[str, Any], ...]\n    events: tuple[_ResolvedEvent, ...]''',
    "claim binding typing",
)
text = replace_once(
    text,
    ''') -> Mapping[str, object]:\n    target = node_bindings[binding.target_mention].node_id''',
    ''') -> dict[str, Any]:\n    target = node_bindings[binding.target_mention].node_id''',
    "resolved attribute typing",
)
text = replace_once(
    text,
    "attribute_by_key: dict[tuple[object, ...], Mapping[str, object]] = {}",
    "attribute_by_key: dict[tuple[object, ...], dict[str, Any]] = {}",
    "attribute map typing",
)

text = replace_regex(
    text,
    r"\n\ndef _ensure_claim_observations\(.*?\n\ndef _apply_event_for_new_claim\(",
    '''\n\ndef _ensure_claim_observations(\n    session: Session,\n    *,\n    claim_id: int,\n    batch_id: int,\n    claim: ClaimProposal,\n    runtime: RuntimeInput,\n    document_id: int,\n) -> int:\n    writes = 0\n    for start, end, quote in _claim_sources(claim, runtime):\n        observation_id, observation_created = promotion_db.ensure_observation(\n            session, document_id, start, end, quote\n        )\n        writes += int(observation_created)\n        writes += int(\n            provenance.add_claim_observation(\n                session, batch_id, claim_id, observation_id\n            )\n        )\n    return writes\n\n\ndef _apply_event_semantics(''',
    "claim observation provenance",
)
# The regex keeps the old function parameters/body after the function name; replace it fully.
text = replace_regex(
    text,
    r"def _apply_event_semantics\(\n    session: Session, event: _ResolvedEvent, claim_id: int\n\) -> int:.*?\n\ndef _apply_new_claim_semantics\(",
    '''def _apply_event_semantics(\n    session: Session,\n    batch_id: int,\n    event: _ResolvedEvent,\n    claim_id: int,\n) -> int:\n    expected = (\n        event.start_at,\n        event.end_at,\n        event.start_precision,\n        event.end_precision,\n    )\n    existing = promotion_db.event_extent(session, event.event_node_id)\n    if existing is not None and existing != expected:\n        raise ValueError("EVENT_TEMPORAL_EXTENT_CONFLICT")\n    writes = int(\n        promotion_db.ensure_event_extent(\n            session,\n            event.event_node_id,\n            start_at=event.start_at,\n            end_at=event.end_at,\n            start_precision=event.start_precision,\n            end_precision=event.end_precision,\n        )\n    )\n    writes += int(\n        provenance.add_event_temporal_basis(\n            session, batch_id, event.event_node_id, claim_id\n        )\n    )\n    return writes\n\n\ndef _apply_claim_semantics(''',
    "event/provenance semantics",
)
text = replace_regex(
    text,
    r"def _apply_claim_semantics\(\n    session: Session,\n    claim_id: int,\n    bindings: _ClaimBindings,\n\) -> int:.*?\n\ndef _write_claim\(",
    '''def _apply_claim_semantics(\n    session: Session,\n    batch_id: int,\n    claim_id: int,\n    bindings: _ClaimBindings,\n) -> int:\n    writes = 0\n    for relation_id, stance in bindings.relations:\n        writes += int(\n            provenance.add_claim_relation(\n                session, batch_id, claim_id, relation_id, stance\n            )\n        )\n    for values in bindings.attributes:\n        if promotion_db.claim_attribute_value_exists(session, claim_id, values):\n            continue\n        provenance.add_claim_attribute_value(\n            session,\n            batch_id,\n            claim_id=claim_id,\n            **values,\n        )\n        writes += 1\n    for event in bindings.events:\n        writes += _apply_event_semantics(\n            session, batch_id, event, claim_id\n        )\n    return writes\n\n\ndef _write_claim(''',
    "claim semantics provenance",
)
text = replace_once(
    text,
    '''        if duplicate.existing.semantic_targets != duplicate.semantic_targets:\n            raise DependencyBlocked216("EXISTING_CLAIM_SEMANTIC_CHANGE_NEEDS_216")''',
    '''        if duplicate.existing.semantic_targets != duplicate.semantic_targets:\n            raise ValueError("CLAIM_DUPLICATE_SEMANTIC_TARGETS_CHANGED")''',
    "claim semantic fail closed",
)
text = replace_once(
    text,
    '''    writes += _ensure_claim_observations(\n        session,\n        claim_id=claim_id,\n        claim_created=claim_created,\n        batch_id=batch_id,\n        claim=claim,\n        runtime=runtime,\n        document_id=document_id,\n    )\n    if claim_created:\n        writes += _apply_new_claim_semantics(session, claim_id, bindings)''',
    '''    writes += _ensure_claim_observations(\n        session,\n        claim_id=claim_id,\n        batch_id=batch_id,\n        claim=claim,\n        runtime=runtime,\n        document_id=document_id,\n    )\n    writes += _apply_claim_semantics(\n        session, batch_id, claim_id, bindings\n    )''',
    "claim reconciliation",
)
text = replace_once(
    text,
    '''    if isinstance(error, DependencyBlocked216):\n        failed = _record_execution_failure(engine, lease, transient=False)\n        return ProductResult(\n            failed.task_status,\n            "DEPENDENCY_BLOCKED_216",\n            error_code="DEPENDENCY_BLOCKED_216",\n        )\n    if isinstance(error, tasks.LeaseLost):''',
    '''    if isinstance(error, tasks.LeaseLost):''',
    "remove dependency failure",
)
text = replace_once(
    text,
    '''            _validate_active_ontology(session, runtime)\n            for resolution in required:\n                _assert_same_alias_noop(session, resolution)\n\n            batch_id = promotion_db.create_batch(session, execution.validator_version)''',
    '''            _validate_active_ontology(session, runtime)\n\n            batch_id = promotion_db.create_batch(session, execution.validator_version)''',
    "official #128 alias path",
)
text = replace_once(
    text,
    '''            if writes == 0:\n                promotion_db.discard_pending_batch(session, batch_id)\n                committed_batch = None\n            else:\n                promotion_db.commit_batch(session, batch_id)\n                committed_batch = batch_id\n            state = tasks.finish_product(session, lease, valid=True)''',
    '''            has_provenance = bool(provenance.changes_for_batch(session, batch_id))\n            if writes == 0 and not has_provenance:\n                promotion_db.discard_pending_batch(session, batch_id)\n                committed_batch = None\n            else:\n                provenance.mark_promotion_committed(session, batch_id)\n                committed_batch = batch_id\n            state = tasks.finish_product(session, lease, valid=True)''',
    "official promotion commit",
)
if "DEPENDENCY_BLOCKED_216" in text or "DependencyBlocked216" in text:
    raise RuntimeError("stale #216 dependency guard remains")
PROMOTION.write_text(text)

# ---- #127 canonical helpers -----------------------------------------------
db = DB_PROMOTION.read_text()
db = replace_once(
    db,
    '''No provider IO, publication work, hidden commit, or promotion provenance schema\nlives here.  Callers own the transaction and must record any #216 provenance\nrequired by mutations of pre-existing canonical objects before committing.''',
    '''No provider IO, publication work, hidden commit, or promotion provenance schema\nlives here. Callers own the transaction. B-3 routes provenance-covered mutations\nthrough the official ontology_map.db.promotion_provenance API.''',
    "db module contract",
)
db = replace_regex(
    db,
    r"\n\ndef commit_batch\(.*?\n\ndef active_topic_identity\(",
    "\n\ndef active_topic_identity(",
    "remove duplicate commit boundary",
)
db = replace_once(
    db,
    '''def insert_attribute_value(\n    session: Session, claim_id: int, values: Mapping[str, object]\n) -> int:\n    return int(\n        session.execute(\n            sa.insert(schema.claim_attribute_value)\n            .values(claim_id=claim_id, **dict(values))\n            .returning(schema.claim_attribute_value.c.claim_attribute_value_id)\n        ).scalar_one()\n    )\n''',
    '''def claim_attribute_value_exists(\n    session: Session, claim_id: int, values: Mapping[str, object]\n) -> bool:\n    expected = canonical_attribute_tuple(values)\n    rows = session.execute(\n        sa.select(schema.claim_attribute_value).where(\n            schema.claim_attribute_value.c.claim_id == claim_id\n        )\n    ).mappings()\n    return any(_attribute_tuple(dict(row)) == expected for row in rows)\n''',
    "attribute exact no-op helper",
)
# Remove bypass writers that B-3 no longer uses. Read/existence helpers are retained.
db = replace_regex(
    db,
    r"\n\ndef add_claim_observation\(.*?\n\ndef claim_relation_exists\(",
    "\n\ndef claim_relation_exists(",
    "remove direct claim observation writer",
)
db = replace_regex(
    db,
    r"\n\ndef add_claim_relation\(.*?\n\ndef claim_attribute_value_exists\(",
    "\n\ndef claim_attribute_value_exists(",
    "remove direct claim relation writer",
)
db = replace_regex(
    db,
    r"\n\ndef add_event_basis\(.*?\n\ndef relation_is_used\(",
    "\n\ndef relation_is_used(",
    "remove direct event basis writer",
)
db = replace_regex(
    db,
    r"\n\ndef same_alias_materialization_is_noop\(.*\Z",
    "\n",
    "remove stale alias guard helper",
)
DB_PROMOTION.write_text(db)

# ---- PostgreSQL regressions -----------------------------------------------
test = TEST.read_text()
test = replace_once(
    test,
    "from ontology_map.db import model_tasks as tasks\nfrom ontology_map.db import schema",
    "from ontology_map.db import model_tasks as tasks\nfrom ontology_map.db import promotion_provenance as provenance\nfrom ontology_map.db import schema",
    "test provenance import",
)
helper_anchor = '''def _count(engine: Engine, table: sa.Table) -> int:\n    with engine.connect() as connection:\n        return int(\n            connection.scalar(sa.select(sa.func.count()).select_from(table)) or 0\n        )\n'''
helper_new = helper_anchor + '''\n\ndef _provenance_kinds(engine: Engine, batch_id: int) -> set[str]:\n    with Session(engine) as session:\n        return {\n            item.change_kind\n            for item in provenance.changes_for_batch(session, batch_id)\n        }\n'''
test = replace_once(test, helper_anchor, helper_new, "provenance test helper")
test = replace_once(
    test,
    '''    assert batch["promotion_status"] == "COMMITTED"\n    assert batch["publication_status"] == "NOT_STARTED"\n    assert task["status"] == "SUCCESS" and task["finished_at"] is not None''',
    '''    assert batch["promotion_status"] == "COMMITTED"\n    assert batch["publication_status"] == "NOT_STARTED"\n    assert task["status"] == "SUCCESS" and task["finished_at"] is not None\n    kinds = _provenance_kinds(case.engine, result.promotion_batch_id)\n    assert {\n        "NODE_ALIAS_CHANGED",\n        "NODE_ALIAS_EVIDENCE_ADDED",\n        "CLAIM_OBSERVATION_ADDED",\n        "CLAIM_RELATION_ADDED",\n        "CLAIM_ATTRIBUTE_VALUE_ADDED",\n        "EVENT_TEMPORAL_BASIS_ADDED",\n    } <= kinds''',
    "new promotion provenance assertion",
)
test = replace_once(
    test,
    '''            schema.event_temporal_basis,\n        )\n    }''',
    '''            schema.event_temporal_basis,\n            provenance.promotion_canonical_change,\n        )\n    }''',
    "noop provenance count before",
)
# There are two copies of the exact table tuple in the same test; replace the next occurrence too.
test = replace_once(
    test,
    '''            schema.event_temporal_basis,\n        )\n    }\n    assert after == before''',
    '''            schema.event_temporal_basis,\n            provenance.promotion_canonical_change,\n        )\n    }\n    assert after == before''',
    "noop provenance count after",
)
test = replace_regex(
    test,
    r"def test_existing_node_alias_mutation_is_dependency_blocked_before_write\(.*?\n\ndef test_conflict_rolls_back_nodes_relation_claim_and_batch",
    '''def test_existing_node_alias_mutation_uses_official_provenance(\n    b3_case: B3Case,\n) -> None:\n    case = b3_case\n    existing = _existing_company(case.engine, "한빛")\n\n    def propose(messages: list[tuple[str, str]]) -> object:\n        payload = ResolutionInput.model_validate_json(messages[1][1])\n        if payload.mention_text == "한빛":\n            assert [item.node_id for item in payload.candidates] == [existing]\n            return {"decision": "SAME", "node_id": existing}\n        return {"decision": "NEW", "node_id": None}\n\n    result = finalize_extraction(\n        case.engine,\n        _runner(case, (case.claims[1],)),\n        case.execution,\n        case.runtime,\n        propose,\n        _claim_new,\n    )\n    assert result.disposition == result.task_status == "SUCCESS"\n    assert result.promotion_batch_id is not None\n    changes = _provenance_kinds(case.engine, result.promotion_batch_id)\n    assert "NODE_ALIAS_EVIDENCE_ADDED" in changes\n    assert "CLAIM_OBSERVATION_ADDED" in changes\n    assert "CLAIM_RELATION_ADDED" in changes\n\n\ndef test_conflict_rolls_back_nodes_relation_claim_and_batch''',
    "replace stale dependency test",
)
test = replace_once(
    test,
    '''        assert _count(engine, schema.promotion_batch) == 0\n        assert _count(engine, schema.knowledge_item) == 0\n        assert _count(engine, schema.observation) == 0''',
    '''        assert _count(engine, schema.promotion_batch) == 0\n        assert _count(engine, schema.knowledge_item) == 0\n        assert _count(engine, schema.observation) == 0\n        assert _count(engine, provenance.promotion_canonical_change) == 0''',
    "rollback provenance assertion",
)
test = replace_once(
    test,
    '''    original_commit = promotion_db.commit_batch''',
    '''    original_commit = provenance.mark_promotion_committed''',
    "retry official commit target",
)
test = replace_once(
    test,
    '''    monkeypatch.setattr(promotion_db, "commit_batch", fail_commit)''',
    '''    monkeypatch.setattr(provenance, "mark_promotion_committed", fail_commit)''',
    "retry monkeypatch official commit",
)
test = replace_once(
    test,
    '''    assert _count(case.engine, schema.observation) == 0\n\n    monkeypatch.setattr(promotion_db, "commit_batch", original_commit)''',
    '''    assert _count(case.engine, schema.observation) == 0\n    assert _count(case.engine, provenance.promotion_canonical_change) == 0\n\n    monkeypatch.setattr(provenance, "mark_promotion_committed", original_commit)''',
    "retry rollback provenance",
)
test = replace_once(
    test,
    '''    assert _count(case.engine, schema.claim) == 2\n    assert _count(case.engine, schema.observation) == 2\n\n\ndef test_allowed_unit_is_effective_input''',
    '''    assert _count(case.engine, schema.claim) == 2\n    assert _count(case.engine, schema.observation) == 2\n    assert _count(case.engine, provenance.promotion_canonical_change) > 0\n\n\ndef test_relation_endpoint_change_is_revalidated_before_promotion(\n    b3_case: B3Case,\n) -> None:\n    case = b3_case\n    with Session(case.engine) as session, session.begin():\n        session.execute(sa.delete(schema.relation_endpoint_rule))\n    result = finalize_extraction(\n        case.engine,\n        _runner(case, (case.claims[1],)),\n        case.execution,\n        case.runtime,\n        _new,\n        _claim_new,\n    )\n    assert result.disposition == result.task_status == "FINAL_FAILED"\n    assert _count(case.engine, schema.promotion_batch) == 0\n    assert _count(case.engine, schema.knowledge_item) == 0\n\n\ndef test_allowed_unit_change_is_revalidated_before_promotion(\n    b3_case: B3Case,\n) -> None:\n    case = b3_case\n    with Session(case.engine) as session, session.begin():\n        revision_id = int(\n            session.scalar(\n                sa.select(schema.attribute_revision.c.attribute_revision_id).where(\n                    schema.attribute_revision.c.is_active\n                )\n            )\n        )\n        session.execute(\n            sa.delete(schema.attribute_revision_allowed_unit).where(\n                schema.attribute_revision_allowed_unit.c.attribute_revision_id\n                == revision_id\n            )\n        )\n        session.execute(\n            sa.insert(schema.attribute_revision_allowed_unit).values(\n                attribute_revision_id=revision_id,\n                allowed_value_kind="NUMBER",\n                unit_code="TB_PER_S",\n            )\n        )\n    result = finalize_extraction(\n        case.engine,\n        _runner(case, (case.claims[0],)),\n        case.execution,\n        case.runtime,\n        _new,\n        _claim_new,\n    )\n    assert result.disposition == result.task_status == "FINAL_FAILED"\n    assert _count(case.engine, schema.promotion_batch) == 0\n    assert _count(case.engine, schema.knowledge_item) == 0\n\n\ndef test_allowed_unit_is_effective_input''',
    "promotion-time relation/unit regressions",
)
if "DEPENDENCY_BLOCKED_216" in test:
    raise RuntimeError("stale dependency expectation remains in tests")
TEST.write_text(test)

print("B-3 #216 provenance wiring staged")
