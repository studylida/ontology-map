"""Canonical knowledge reuse and caller-owned writes; no model calls or commits."""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from struct import pack
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from ontology_map import entity_resolution as er
from ontology_map.db import schema as db
from ontology_map.entity_resolution_contracts import PromotionNodeBinding, Resolution
from ontology_map.extraction_contracts import (
    AttributeProposal, ClaimProposal, EventTimeProposal, NumberValue,
    RelationProposal, SourceDocument, SourceSpan, StringValue,
)
from ontology_map.knowledge_extraction_contracts import (
    PreparedClaim, References, canonical,
)


def mention_key(candidate: str, mention: str) -> str:
    return canonical([candidate, mention]).decode("utf-8")


def relation_identity(source: int, target: int, revision: int, direction: str) -> tuple[int, int, bytes]:
    if direction == "SYMMETRIC":
        source, target = sorted((source, target))
    return source, target, sha256(b"REL1" + pack(">qqq", source, revision, target)).digest()


def _instant(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat()


def _number_text(value: Decimal) -> str:
    if not value.is_finite():
        raise ValueError("NONFINITE_NUMBER")
    if value.is_zero():
        return "0"
    sign, raw, exponent = value.as_tuple()
    digits = list(raw)
    scale = int(exponent)
    while digits[-1] == 0:
        digits.pop()
        scale += 1
    return ("-" if sign else "") + "".join(map(str, digits)) + f"e{scale}"


def proposed_facts(
    claim: ClaimProposal, node_ids: Mapping[str, int], refs: References,
) -> list[dict[str, Any]]:
    relations = {r.code: r for r in refs.ontology.relations}
    attributes = {a.code: a for a in refs.ontology.attributes}
    facts: list[dict[str, Any]] = []
    for binding in claim.bindings:
        if isinstance(binding, RelationProposal):
            rule = relations[binding.code]
            if rule.revision_id is None:
                raise ValueError("UNREGISTERED_RELATION_REVISION")
            source, target, _ = relation_identity(
                node_ids[binding.source_mention], node_ids[binding.target_mention],
                rule.revision_id, rule.direction,
            )
            facts.append({"kind": "RELATION", "source": source, "target": target,
                          "revision": rule.revision_id, "stance": binding.stance})
        elif isinstance(binding, AttributeProposal):
            rule_a = attributes[binding.code]
            value = binding.value
            if not isinstance(value, (StringValue, NumberValue)):
                raise ValueError("UNAPPROVED_ATTRIBUTE_VALUE_KIND")
            scalar = str(value.value) if isinstance(value, StringValue) else _number_text(value.value)
            facts.append({"kind": "ATTRIBUTE", "target": node_ids[binding.target_mention],
                          "revision": rule_a.revision_id, "value_kind": value.kind,
                          "value": scalar, "unit": value.unit if isinstance(value, NumberValue) else None})
        else:
            facts.append({"kind": "EVENT_TIME", "target": node_ids[binding.event_mention],
                          "start": _instant(binding.start.value), "end": _instant(binding.end.value),
                          "start_precision": binding.start.precision,
                          "end_precision": binding.end.precision})
    relations_seen: dict[tuple[int, int, int], str] = {}
    for fact in facts:
        if fact["kind"] != "RELATION":
            continue
        key = (fact["source"], fact["target"], fact["revision"])
        if key in relations_seen and relations_seen[key] != fact["stance"]:
            raise ValueError("CONTRADICTORY_BINDINGS_WITHIN_CLAIM")
        relations_seen[key] = fact["stance"]
    return sorted({canonical(f): f for f in facts}.values(), key=canonical)


def existing_nodes(claim: ClaimProposal, resolutions: Sequence[Resolution]) -> dict[str, int] | None:
    by_id = {r.mention.mention_id: r for r in resolutions}
    result: dict[str, int] = {}
    for mention in claim.mentions:
        resolved = by_id[mention_key(claim.candidate_id, mention.mention_id)]
        if resolved.node_id is None or resolved.decision != "SAME":
            return None
        result[mention.mention_id] = resolved.node_id
    return result


def usable(session: Session, item_id: int, kind: str, batch_id: int | None = None) -> bool:
    return bool(session.execute(sa.text("""
        SELECT EXISTS (
          SELECT 1 FROM knowledge_item k JOIN promotion_batch b USING (promotion_batch_id)
          WHERE k.knowledge_item_id=:id AND k.item_kind=:kind
            AND k.current_state IN ('EVIDENCE_VERIFIED', 'HUMAN_VERIFIED')
            AND (b.promotion_status='COMMITTED' OR
                 (b.promotion_batch_id=:batch AND b.promotion_status='PENDING'))
            AND NOT EXISTS (
              SELECT 1 FROM lint_finding f JOIN lint_policy_rule p USING (lint_policy_rule_id)
              WHERE f.knowledge_item_id=k.knowledge_item_id AND f.resolved_at IS NULL
                AND p.severity='BLOCKING'
            )
        )
    """), {"id": item_id, "kind": kind, "batch": batch_id}).scalar_one())


def stored_facts(session: Session, claim_id: int) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for row in session.execute(sa.text("""
        SELECT r.source_node_id, r.target_node_id, r.relation_type_revision_id, cr.stance
        FROM claim_relation cr JOIN relation r USING (relation_id) WHERE cr.claim_id=:id
    """), {"id": claim_id}).mappings():
        facts.append({"kind": "RELATION", "source": int(row["source_node_id"]),
                      "target": int(row["target_node_id"]),
                      "revision": int(row["relation_type_revision_id"]), "stance": row["stance"]})
    for row in session.execute(sa.select(db.claim_attribute_value).where(db.claim_attribute_value.c.claim_id == claim_id)).mappings():
        if row["value_kind"] not in ("STRING", "NUMBER"):
            # Existing unsupported facts must not disappear during comparison.
            return [{"kind": "UNSUPPORTED_EXISTING_VALUE"}]
        value = row["string_value"]
        if row["value_kind"] == "NUMBER":
            value = _number_text(Decimal(row["number_value"]))
        facts.append({"kind": "ATTRIBUTE", "target": int(row["target_node_id"]),
                      "revision": int(row["attribute_revision_id"]),
                      "value_kind": row["value_kind"], "value": value,
                      "unit": row["unit_code"]})
    for row in session.execute(sa.text("""
        SELECT e.* FROM event_temporal_basis b
        JOIN event_temporal_extent e USING (event_node_id) WHERE b.claim_id=:id
    """), {"id": claim_id}).mappings():
        facts.append({"kind": "EVENT_TIME", "target": int(row["event_node_id"]),
                      "start": _instant(row["start_at"]), "end": _instant(row["end_at"]),
                      "start_precision": row["start_precision"], "end_precision": row["end_precision"]})
    return sorted({canonical(f): f for f in facts}.values(), key=canonical)


def claim_snapshot(session: Session, claim_id: int) -> dict[str, Any]:
    row = session.execute(sa.select(db.claim).where(db.claim.c.claim_id == claim_id)).mappings().one()
    evidence = list(session.execute(sa.text("""
        SELECT o.source_document_id, o.start_char, o.end_char, o.quote_text
        FROM claim_observation co JOIN observation o USING (observation_id)
        WHERE co.claim_id=:id ORDER BY o.source_document_id, o.start_char, o.end_char
    """), {"id": claim_id}).mappings())
    return {
        "claim_id": claim_id, "statement": row["statement_text"], "language": row["language"],
        "modality": row["modality"], "asserted_from": _instant(row["asserted_from"]),
        "asserted_to": _instant(row["asserted_to"]),
        "asserted_from_precision": row["asserted_from_precision"],
        "asserted_to_precision": row["asserted_to_precision"],
        "facts": stored_facts(session, claim_id), "evidence": [dict(e) for e in evidence],
    }


def claim_candidates(
    session: Session, claim: ClaimProposal, nodes: Mapping[str, int], refs: References,
    language: str,
) -> list[dict[str, Any]]:
    stmt = sa.text("""
        SELECT DISTINCT c.claim_id FROM claim c
        WHERE c.modality=:modality AND c.language=:language
          AND c.asserted_from IS NULL AND c.asserted_to IS NULL AND (
            EXISTS (SELECT 1 FROM claim_relation cr JOIN relation r USING (relation_id)
                    WHERE cr.claim_id=c.claim_id
                      AND (r.source_node_id IN :nodes OR r.target_node_id IN :nodes))
            OR EXISTS (SELECT 1 FROM claim_attribute_value a
                       WHERE a.claim_id=c.claim_id AND a.target_node_id IN :nodes)
            OR EXISTS (SELECT 1 FROM event_temporal_basis e
                       WHERE e.claim_id=c.claim_id AND e.event_node_id IN :nodes)
          ) ORDER BY c.claim_id
    """).bindparams(sa.bindparam("nodes", expanding=True))
    facts = proposed_facts(claim, nodes, refs)
    result: list[dict[str, Any]] = []
    for candidate_id in session.execute(stmt, {"nodes": sorted(set(nodes.values())),
                                              "modality": claim.modality, "language": language}).scalars():
        candidate_id = int(candidate_id)
        if not usable(session, candidate_id, "CLAIM"):
            continue
        snapshot = claim_snapshot(session, candidate_id)
        if snapshot["facts"] == facts and snapshot["evidence"]:
            result.append(snapshot)
    return result


def storage_binding_allowed(
    session: Session, binding: Any, claim: ClaimProposal, resolutions: Sequence[Resolution], refs: References,
) -> bool:
    by_id = {r.mention.mention_id: r for r in resolutions}
    if isinstance(binding, AttributeProposal):
        return binding.code in _attribute_codes(refs)
    if isinstance(binding, EventTimeProposal):
        resolved = by_id[mention_key(claim.candidate_id, binding.event_mention)]
        if resolved.node_id is None:
            return True
        existing = session.execute(sa.select(db.event_temporal_extent).where(
            db.event_temporal_extent.c.event_node_id == resolved.node_id,
        )).mappings().one_or_none()
        return existing is None or (
            _instant(existing["start_at"]) == _instant(binding.start.value)
            and _instant(existing["end_at"]) == _instant(binding.end.value)
            and existing["start_precision"] == binding.start.precision
            and existing["end_precision"] == binding.end.precision
        )
    source = by_id[mention_key(claim.candidate_id, binding.source_mention)].node_id
    target = by_id[mention_key(claim.candidate_id, binding.target_mention)].node_id
    if source is None or target is None:
        return binding.stance == "SUPPORT"
    rule = next(r for r in refs.ontology.relations if r.code == binding.code)
    _, _, key = relation_identity(source, target, int(rule.revision_id or 0), rule.direction)
    existing_id = session.execute(sa.select(db.relation.c.relation_id).where(db.relation.c.relation_identity_key == key)).scalar_one_or_none()
    if existing_id is None:
        return binding.stance == "SUPPORT"
    return usable(session, int(existing_id), "RELATION") and _has_support(session, int(existing_id))


def _attribute_codes(refs: References) -> set[str]:
    return {a.code for a in refs.ontology.attributes}


def _item(session: Session, kind: str, batch_id: int) -> int:
    return int(session.execute(sa.insert(db.knowledge_item).values(
        item_kind=kind, current_state="EVIDENCE_VERIFIED", promotion_batch_id=batch_id,
    ).returning(db.knowledge_item.c.knowledge_item_id)).scalar_one())


def ensure_relation(session: Session, fact: Mapping[str, Any], batch_id: int, refs: References) -> int:
    rule = next(r for r in refs.ontology.relations if r.revision_id == fact["revision"])
    source, target, key = relation_identity(int(fact["source"]), int(fact["target"]), int(fact["revision"]), rule.direction)
    # Serialize get-or-create without leaking an unused knowledge_item on conflict.
    session.execute(sa.text("SELECT pg_advisory_xact_lock(:key)"), {"key": int.from_bytes(key[:8], "big", signed=True)})
    existing = session.execute(sa.select(db.relation).where(db.relation.c.relation_identity_key == key)).mappings().one_or_none()
    if existing is not None:
        if not usable(session, int(existing["relation_id"]), "RELATION", batch_id):
            raise ValueError("EXISTING_RELATION_NOT_USABLE")
        if (existing["source_node_id"], existing["target_node_id"], existing["relation_type_revision_id"]) != (source, target, fact["revision"]):
            raise ValueError("RELATION_IDENTITY_MISMATCH")
        return int(existing["relation_id"])
    relation_id = _item(session, "RELATION", batch_id)
    session.execute(sa.insert(db.relation).values(
        relation_id=relation_id, source_node_id=source, target_node_id=target,
        relation_type_revision_id=fact["revision"], relation_identity_key=key,
    ))
    return relation_id


def _has_support(session: Session, relation_id: int, batch_id: int | None = None) -> bool:
    ids = session.execute(sa.text("""
        SELECT cr.claim_id FROM claim_relation cr
        WHERE cr.relation_id=:id AND cr.stance='SUPPORT'
          AND EXISTS (SELECT 1 FROM claim_observation co WHERE co.claim_id=cr.claim_id)
    """), {"id": relation_id}).scalars()
    return any(usable(session, int(i), "CLAIM", batch_id) for i in ids)


def _observation(session: Session, document: SourceDocument, source: SourceSpan) -> int:
    body = document.body
    if body[source.start:source.end] != source.quote or sha256(source.quote.encode()).hexdigest() != source.quote_hash:
        raise ValueError("SOURCE_CHANGED_BEFORE_WRITE")
    session.execute(sa.text("""
        INSERT INTO observation
          (source_document_id, start_char, end_char, quote_text, quote_hash, observed_at)
        VALUES (:document, :start, :end, :quote, :hash, clock_timestamp())
        ON CONFLICT (source_document_id, start_char, end_char) DO NOTHING
    """), {"document": int(document.document_id), "start": source.start, "end": source.end,
            "quote": source.quote, "hash": bytes.fromhex(source.quote_hash)})
    row = session.execute(sa.text("""
        SELECT observation_id, quote_text, quote_hash FROM observation
        WHERE source_document_id=:document AND start_char=:start AND end_char=:end
    """), {"document": int(document.document_id), "start": source.start, "end": source.end}).mappings().one()
    if row["quote_text"] != source.quote or bytes(row["quote_hash"]).hex() != source.quote_hash:
        raise ValueError("OBSERVATION_IDENTITY_MISMATCH")
    return int(row["observation_id"])


def _write_fact(session: Session, claim_id: int, fact: dict[str, Any], refs: References, batch_id: int) -> int | None:
    if fact["kind"] == "RELATION":
        relation_id = ensure_relation(session, fact, batch_id, refs)
        session.execute(sa.text("""
            INSERT INTO claim_relation (claim_id, relation_id, stance)
            VALUES (:claim, :relation, :stance)
            ON CONFLICT (claim_id, relation_id) DO NOTHING
        """), {"claim": claim_id, "relation": relation_id, "stance": fact["stance"]})
        return relation_id
    if fact["kind"] == "ATTRIBUTE":
        session.execute(sa.insert(db.claim_attribute_value).values(
            claim_id=claim_id, target_node_id=fact["target"], attribute_revision_id=fact["revision"],
            value_kind=fact["value_kind"],
            string_value=fact["value"] if fact["value_kind"] == "STRING" else None,
            number_value=Decimal(fact["value"]) if fact["value_kind"] == "NUMBER" else None,
            unit_code=fact["unit"], date_from_precision="UNKNOWN", date_to_precision="UNKNOWN",
        ))
        return None
    session.execute(sa.text("""
        INSERT INTO event_temporal_extent
          (event_node_id, start_at, end_at, start_precision, end_precision)
        VALUES (:target, :start, :end, :start_precision, :end_precision)
        ON CONFLICT (event_node_id) DO NOTHING
    """), fact)
    row = session.execute(sa.select(db.event_temporal_extent).where(db.event_temporal_extent.c.event_node_id == fact["target"])).mappings().one()
    if (_instant(row["start_at"]), _instant(row["end_at"]), row["start_precision"], row["end_precision"]) != (fact["start"], fact["end"], fact["start_precision"], fact["end_precision"]):
        raise ValueError("EVENT_TIME_CHANGED_OR_INCOMPATIBLE")
    session.execute(sa.insert(db.event_temporal_basis).values(event_node_id=fact["target"], claim_id=claim_id))
    return None


def write_prepared(
    session: Session, batch_id: int, document: SourceDocument, refs: References,
    claims: Sequence[PreparedClaim], language: str,
) -> tuple[int, ...]:
    resolutions = tuple(r for prepared in claims for r in prepared.resolutions)
    dependencies = {p.claim.candidate_id: [r.mention.mention_id for r in p.resolutions] for p in claims}
    selected = er.select_resolvable_knowledge(resolutions, dependencies)
    if set(selected.accepted) != set(dependencies):
        raise ValueError("UNRESOLVED_PROMOTION_DEPENDENCY")
    # Revalidate existing Claim snapshots once before adding any new evidence.
    for claim_id in sorted({p.existing_claim_id for p in claims if p.existing_claim_id is not None}):
        session.execute(sa.select(db.knowledge_item).where(db.knowledge_item.c.knowledge_item_id == claim_id).with_for_update())
        signature = canonical(claim_snapshot(session, claim_id))
        if not usable(session, claim_id, "CLAIM") or any(p.existing_signature != signature for p in claims if p.existing_claim_id == claim_id):
            raise ValueError("REUSED_CLAIM_SNAPSHOT_CHANGED")
    ids: list[int] = []
    relation_ids: set[int] = set()
    with er.resolved_nodes_for_promotion(session, batch_id, resolutions, selected.mention_ids) as bindings:
        for prepared in claims:
            claim_id, used = _write_claim(session, batch_id, document, refs, prepared, bindings, language)
            ids.append(claim_id)
            relation_ids.update(used)
        if not all(_has_support(session, rid, batch_id) for rid in relation_ids):
            raise ValueError("RELATION_WITHOUT_EVIDENCED_SUPPORT")
    return tuple(ids)


def _write_claim(
    session: Session, batch_id: int, document: SourceDocument, refs: References,
    prepared: PreparedClaim, bindings: Mapping[str, PromotionNodeBinding], language: str,
) -> tuple[int, set[int]]:
    claim = prepared.claim
    nodes = {m.mention_id: bindings[mention_key(claim.candidate_id, m.mention_id)].node_id for m in claim.mentions}
    facts = proposed_facts(claim, nodes, refs)
    claim_id = prepared.existing_claim_id
    relation_ids: set[int] = set()
    if claim_id is None:
        claim_id = _item(session, "CLAIM", batch_id)
        session.execute(sa.insert(db.claim).values(
            claim_id=claim_id, statement_text=claim.statement, language=language,
            modality=claim.modality, asserted_from_precision="UNKNOWN", asserted_to_precision="UNKNOWN",
        ))
        for fact in facts:
            relation_id = _write_fact(session, claim_id, fact, refs, batch_id)
            if relation_id is not None:
                relation_ids.add(relation_id)
    else:
        # No rewrite or destructive merge of the existing Claim or its facts.
        session.execute(sa.select(db.knowledge_item).where(db.knowledge_item.c.knowledge_item_id == claim_id).with_for_update())
        snapshot = claim_snapshot(session, claim_id)
        if not usable(session, claim_id, "CLAIM") or snapshot["facts"] != facts:
            raise ValueError("REUSED_CLAIM_SNAPSHOT_CHANGED")
    for source in prepared.evidence:
        observation_id = _observation(session, document, source)
        session.execute(sa.text("""
            INSERT INTO claim_observation (claim_id, observation_id)
            VALUES (:claim, :observation) ON CONFLICT DO NOTHING
        """), {"claim": claim_id, "observation": observation_id})
    return claim_id, relation_ids
