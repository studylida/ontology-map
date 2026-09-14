"""Read immutable source/active references and enqueue an idempotent product task."""

from dataclasses import asdict
from hashlib import sha256
from typing import Any, cast

import sqlalchemy as sa
from sqlalchemy.orm import Session

from ontology_map import extraction
from ontology_map.entity_resolution import PROMPT_VERSION as ER_PROMPT_VERSION
from ontology_map.entity_resolution_contracts import APPROVED_TOPICS, ResolutionProposal
from ontology_map.extraction_contracts import (
    AttributeRule, BodySelection, ClaimSupport, KnowledgeProposals, MeaningSupport,
    NodeType, Ontology, RelationRule, SourceDocument, SourceSpan, digest,
)
from ontology_map.knowledge_extraction_contracts import (
    ATTRIBUTES, RELATIONS, PROMPT_VERSION, VALIDATOR_VERSION,
    References, WorkerOptions, canonical, task_key,
)
from ontology_map.model_studio import FLASH, PLUS


def load_document(session: Session, document_id: int) -> SourceDocument:
    row = session.execute(sa.text("""
        SELECT normalized_body, body_hash FROM source_document
        WHERE source_document_id=:id
    """), {"id": document_id}).mappings().one()
    body = str(row["normalized_body"])
    # Stable line projection, with exact original Unicode offsets; no rewriting.
    spans: list[SourceSpan] = []
    start = 0
    for index, line in enumerate(body.splitlines(keepends=True)):
        end = start + len(line)
        if line.strip():
            spans.append(SourceSpan(
                source_id=f"s{index + 1}", start=start, end=end, quote=line,
                quote_hash=digest(line), paragraph_id=None,
            ))
        start = end
    return SourceDocument(
        document_id=str(document_id), body=body,
        body_hash=bytes(row["body_hash"]).hex(), sources=tuple(spans),
    )


def _relations(session: Session) -> tuple[list[RelationRule], list[str]]:
    rows = session.execute(sa.text("""
        SELECT t.relation_code, r.relation_type_revision_id, r.version_no,
               r.display_name, r.directionality
        FROM relation_type t JOIN relation_type_revision r USING (relation_type_id)
        WHERE r.is_active ORDER BY t.relation_code
    """)).mappings().all()
    accepted: list[RelationRule] = []
    unavailable = set(RELATIONS)
    for row in rows:
        code = str(row["relation_code"])
        if code not in RELATIONS:
            continue
        pairs = session.execute(sa.text("""
            SELECT s.node_type_code AS source, t.node_type_code AS target
            FROM relation_endpoint_rule e
            JOIN node_type s ON s.node_type_id=e.source_node_type_id
            JOIN node_type t ON t.node_type_id=e.target_node_type_id
            WHERE e.relation_type_revision_id=:id
            ORDER BY s.node_type_code, t.node_type_code
        """), {"id": row["relation_type_revision_id"]}).all()
        endpoints = tuple((str(r[0]), str(r[1])) for r in pairs)
        direction, approved = RELATIONS[code]
        if row["directionality"] != direction or set(endpoints) != set(approved):
            continue
        accepted.append(RelationRule(
            code=code, version_no=int(row["version_no"]),
            revision_id=int(row["relation_type_revision_id"]),
            description=str(row["display_name"]),
            direction=cast(Any, direction), endpoints=cast(Any, endpoints),
        ))
        unavailable.remove(code)
    return accepted, sorted(unavailable)


def _attributes(session: Session) -> tuple[list[AttributeRule], list[str]]:
    rows = session.execute(sa.text("""
        SELECT a.attribute_code, r.attribute_revision_id, r.version_no,
          r.display_name, n.node_type_code, r.allowed_value_kind, r.unit_rule
        FROM attribute a JOIN attribute_revision r USING (attribute_id)
        JOIN node_type n ON n.node_type_id=r.target_node_type_id
        WHERE r.is_active ORDER BY a.attribute_code
    """)).mappings().all()
    accepted: list[AttributeRule] = []
    unavailable = set(ATTRIBUTES) | {"MAX_MEMORY_BANDWIDTH"}
    for row in rows:
        code = str(row["attribute_code"])
        actual = (row["node_type_code"], row["allowed_value_kind"], row["unit_rule"])
        if code not in ATTRIBUTES or actual != ATTRIBUTES[code]:
            continue
        accepted.append(AttributeRule(
            code=code, version_no=int(row["version_no"]),
            revision_id=int(row["attribute_revision_id"]),
            description=str(row["display_name"]), node_type=row["node_type_code"],
            value_kind=row["allowed_value_kind"],
            units=() if row["unit_rule"] is None else (str(row["unit_rule"]),),
        ))
        unavailable.remove(code)
    return accepted, sorted(unavailable)


def load_references(session: Session) -> References:
    contract = session.execute(sa.text("""
        SELECT output_schema_definition_id, version_no, schema_json
        FROM output_schema_definition
        WHERE task_kind='KNOWLEDGE_EXTRACTION' AND is_active
    """)).mappings().one_or_none()
    if contract is None or contract["schema_json"] != KnowledgeProposals.model_json_schema():
        raise ValueError("ACTIVE_EXTRACTION_OUTPUT_CONTRACT_MISSING_OR_MISMATCHED")
    policy = session.execute(sa.text("""
        SELECT lint_policy_version_id, validator_version
        FROM lint_policy_version WHERE is_active
    """)).mappings().one_or_none()
    if policy is None or policy["validator_version"] != VALIDATOR_VERSION:
        raise ValueError("ACTIVE_EXTRACTION_VALIDATOR_MISSING_OR_MISMATCHED")
    rules = session.execute(sa.text("""
        SELECT p.lint_policy_rule_id, p.severity, r.rule_code, r.evaluation_scope
        FROM lint_policy_rule p JOIN lint_rule r USING (lint_rule_id)
        WHERE p.lint_policy_version_id=:id
    """), {"id": policy["lint_policy_version_id"]}).mappings().all()
    if len(rules) != 1 or (
        rules[0]["rule_code"] != "EVIDENCE_TRACE_COMPLETE"
        or rules[0]["severity"] != "BLOCKING"
        or rules[0]["evaluation_scope"] not in ("BOTH", "PRE_PROMOTION")
    ):
        # An unknown active validator must not be silently treated as implemented.
        raise ValueError("UNSUPPORTED_ACTIVE_LINT_POLICY")
    nodes = session.execute(sa.text("""
        SELECT node_type_code FROM node_type WHERE is_active
        ORDER BY node_type_code
    """)).scalars().all()
    allowed = {"COMPANY", "PERSON", "TECHNOLOGY", "EVENT", "TOPIC"}
    types = tuple(cast(NodeType, str(code)) for code in nodes if code in allowed)
    relations, missing_relations = _relations(session)
    attributes, missing_attributes = _attributes(session)
    if not types or not (relations or attributes):
        raise ValueError("ACTIVE_APPROVED_ONTOLOGY_MISSING")
    return References(
        int(contract["output_schema_definition_id"]), int(contract["version_no"]),
        Ontology(node_types=types, relations=tuple(relations),
                 attributes=tuple(attributes), topics=tuple(sorted(APPROVED_TOPICS))),
        int(policy["lint_policy_version_id"]), int(rules[0]["lint_policy_rule_id"]),
        tuple(missing_relations + missing_attributes),
    )


def input_hash(document: SourceDocument, refs: References, options: WorkerOptions) -> bytes:
    return sha256(canonical({
        "document": document.model_dump(mode="json"),
        "references": {"schema_id": refs.schema_id, "schema_version": refs.schema_version,
                       "ontology": refs.ontology.model_dump(mode="json"),
                       "lint_policy_id": refs.lint_policy_id,
                       "evidence_rule_id": refs.evidence_rule_id},
        "options": asdict(options), "validator": VALIDATOR_VERSION,
        "helper_models": [FLASH, PLUS],
        "helper_prompts": [extraction.BODY_PROMPT, extraction.GENERATION_PROMPT, extraction.CLAIM_PROMPT,
                           extraction.MEANING_PROMPT, ER_PROMPT_VERSION],
        "schemas": [c.model_json_schema() for c in (
            BodySelection, ClaimSupport, MeaningSupport, ResolutionProposal,
        )],
    })).digest()


def enqueue(session: Session, document_id: int, options: WorkerOptions) -> int:
    document, refs = load_document(session, document_id), load_references(session)
    effective_hash = input_hash(document, refs, options)
    key = task_key(effective_hash, FLASH, refs.schema_id)
    session.execute(sa.text("""
        INSERT INTO model_task
          (task_kind, source_document_id, input_hash, output_schema_definition_id,
           model_version, prompt_version, cache_key)
        VALUES ('KNOWLEDGE_EXTRACTION', :document, :input_hash, :schema,
                :model, :prompt, :cache_key)
        ON CONFLICT (cache_key) DO NOTHING
    """), {"document": document_id, "input_hash": effective_hash, "schema": refs.schema_id,
            "model": FLASH, "prompt": PROMPT_VERSION, "cache_key": key})
    return int(session.execute(sa.text("""
        SELECT model_task_id FROM model_task WHERE cache_key=:key
    """), {"key": key}).scalar_one())


def require_effective_input(
    session: Session, task_id: int, options: WorkerOptions,
) -> tuple[SourceDocument, References]:
    task = session.execute(sa.text("""
        SELECT * FROM model_task WHERE model_task_id=:id
    """), {"id": task_id}).mappings().one()
    if task["task_kind"] != "KNOWLEDGE_EXTRACTION" or task["source_document_id"] is None:
        raise ValueError("INVALID_EXTRACTION_TASK")
    document = load_document(session, int(task["source_document_id"]))
    refs = load_references(session)
    effective_hash = input_hash(document, refs, options)
    if (
        bytes(task["input_hash"]) != effective_hash
        or task["output_schema_definition_id"] != refs.schema_id
        or task["model_version"] != FLASH or task["prompt_version"] != PROMPT_VERSION
        or bytes(task["cache_key"]) != task_key(effective_hash, FLASH, refs.schema_id)
    ):
        raise ValueError("EFFECTIVE_INPUT_CHANGED_REPROCESS_REQUIRED")
    return document, refs


def record_evidence_blocks(
    session: Session, document: SourceDocument, refs: References,
    proposals: KnowledgeProposals, exclusions: list[tuple[str, str]],
) -> None:
    evidence_codes = {"SOURCE_REFERENCE", "EMPTY_EVIDENCE"}
    failed = {candidate for candidate, code in exclusions if code in evidence_codes}
    for claim in proposals.claims:
        if claim.candidate_id not in failed:
            continue
        fingerprint = sha256(canonical(claim.model_dump(mode="json", exclude={"candidate_id"}))).digest()
        session.execute(sa.text("""
            INSERT INTO blocked_fingerprint
              (fingerprint, source_document_id, output_schema_definition_id,
               lint_policy_rule_id, first_blocked_at, last_blocked_at, blocked_count)
            VALUES (:key, :source, :contract, :rule, clock_timestamp(), clock_timestamp(), 1)
            ON CONFLICT (fingerprint, source_document_id, output_schema_definition_id, lint_policy_rule_id)
            DO UPDATE SET last_blocked_at=clock_timestamp(),
                          blocked_count=blocked_fingerprint.blocked_count+1
        """), {"key": fingerprint, "source": int(document.document_id),
                "contract": refs.schema_id, "rule": refs.evidence_rule_id})
