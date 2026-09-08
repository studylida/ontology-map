"""현재 공개 snapshot의 패널 조회. 원문·Claim 사본을 만들지 않는다."""

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from ontology_map.db.exploration import _PUBLIC_NODES_CTE, get_center


def context(session: Session, node_id: int) -> dict[str, Any] | None:
    center = get_center(session, node_id)
    if center is None:
        return None
    row = (
        session.execute(
            sa.text("""
        SELECT node_context_id, node_search_document_id FROM node_context
        WHERE node_context_id = :context_id
    """),
            {"context_id": center.node_context_id},
        )
        .mappings()
        .one()
    )
    return dict(row)


def basis(session: Session, document_id: int) -> tuple[list[int], bool]:
    rows = (
        session.execute(
            sa.text("""
        SELECT b.knowledge_item_id,
          ki.current_state IN ('EVIDENCE_VERIFIED', 'HUMAN_VERIFIED')
          AND pb.promotion_status = 'COMMITTED' AND pb.publication_status = 'READY'
          AND NOT EXISTS (
            SELECT 1 FROM lint_finding lf JOIN lint_policy_rule lpr USING
            (lint_policy_rule_id)
            WHERE lf.knowledge_item_id = b.knowledge_item_id
              AND lf.resolved_at IS NULL AND lpr.severity = 'BLOCKING'
          ) AS visible
        FROM search_document_basis b
        JOIN knowledge_item ki USING (knowledge_item_id)
        JOIN promotion_batch pb USING (promotion_batch_id)
        WHERE b.node_search_document_id = :document_id
    """),
            {"document_id": document_id},
        )
        .mappings()
        .all()
    )
    return [int(r["knowledge_item_id"]) for r in rows if r["visible"]], bool(
        rows
    ) and all(r["visible"] for r in rows)


_NODE_CLAIMS = (
    _PUBLIC_NODES_CTE
    + """
, connected_relations AS (
 SELECT relation_id AS target_id FROM relation
 WHERE :node_id IN (source_node_id, target_node_id) AND relation_id = ANY(:basis_ids)
   AND source_node_id IN (SELECT node_id FROM public_nodes)
   AND target_node_id IN (SELECT node_id FROM public_nodes)
), connected AS (
    SELECT cr.claim_id, 'RELATION' AS kind, r.relation_id AS target_id,
      cr.stance AS position
    FROM claim_relation cr JOIN relation r USING (relation_id)
    WHERE :node_id IN (r.source_node_id, r.target_node_id)
      AND r.relation_id = ANY(:basis_ids)
      AND r.source_node_id IN (SELECT node_id FROM public_nodes)
      AND r.target_node_id IN (SELECT node_id FROM public_nodes)
    UNION
    SELECT cav.claim_id, 'ATTRIBUTE', cav.attribute_revision_id, NULL
    FROM claim_attribute_value cav WHERE cav.target_node_id = :node_id
    UNION
    SELECT etb.claim_id, 'EVENT_TIME', etb.event_node_id, NULL
    FROM event_temporal_basis etb WHERE etb.event_node_id = :node_id
    UNION
    SELECT cm.claim_id, 'CONFLICT', cs.conflict_set_id, cm.position_key
    FROM conflict_set cs JOIN conflict_member cm USING (conflict_set_id)
    WHERE cs.current_state IN ('AGENT_PROPOSED', 'HUMAN_CONFIRMED')
      AND (cs.target_node_id = :node_id OR cs.event_node_id = :node_id OR
        cs.relation_id IN (SELECT target_id FROM connected_relations))
), selected AS (
    SELECT c.claim_id, c.statement_text, c.modality, ki.current_state,
      count(DISTINCT sd.evidence_group_id) FILTER (
        WHERE sd.published_at >= :start_at AND sd.published_at < :as_of_at
      )::integer AS evidence_group_count,
      max(sd.published_at) FILTER (WHERE sd.published_at < :as_of_at) AS
      last_published_at
    FROM claim c JOIN knowledge_item ki ON ki.knowledge_item_id = c.claim_id
    JOIN claim_observation co USING (claim_id)
    JOIN observation o USING (observation_id)
    JOIN source_document sd USING (source_document_id)
    WHERE c.claim_id = ANY(:basis_ids) AND c.claim_id IN (SELECT claim_id FROM
    connected)
    GROUP BY c.claim_id, c.statement_text, c.modality, ki.current_state
)
"""
)


def node_claims(session: Session, params: dict[str, Any]) -> list[dict[str, Any]]:
    rows = session.execute(
        sa.text(
            _NODE_CLAIMS
            + """
        SELECT * FROM selected WHERE evidence_group_count > 0
          AND claim_id > :after_id ORDER BY claim_id LIMIT :limit
    """
        ),
        params,
    ).mappings()
    return [dict(row) for row in rows]


def claim_connections(session: Session, params: dict[str, Any]) -> list[dict[str, Any]]:
    rows = session.execute(
        sa.text(
            _NODE_CLAIMS
            + """
        SELECT DISTINCT kind, target_id, position,
          CASE kind
          WHEN 'RELATION' THEN (
            SELECT a.alias_text || ' · ' || rt.display_name || ' · ' || b.alias_text
            FROM relation r JOIN relation_type_revision rt
              USING (relation_type_revision_id)
            JOIN node_alias a ON a.node_id = r.source_node_id AND a.is_preferred
            JOIN node_alias b ON b.node_id = r.target_node_id AND b.is_preferred
            WHERE r.relation_id = connected.target_id)
          WHEN 'ATTRIBUTE' THEN (SELECT display_name FROM attribute_revision
            WHERE attribute_revision_id = connected.target_id)
          WHEN 'EVENT_TIME' THEN '사건의 채택 시간'
          ELSE '같은 대상에 관한 엇갈리는 주장'
          END AS label
        FROM connected
        WHERE claim_id = :claim_id ORDER BY kind, target_id, position
    """
        ),
        params,
    ).mappings()
    return [dict(row) for row in rows]


def trace_rows(
    session: Session, claim_id: int, after_id: int = 0, limit: int = 21
) -> list[dict[str, Any]]:
    rows = session.execute(
        sa.text("""
        SELECT o.observation_id, sd.source_document_id, sd.title, sd.publisher_name,
          sd.published_at, sd.published_precision, sd.canonical_url,
          o.quote_text, o.paragraph_number, o.start_char, o.end_char
        FROM claim_observation co JOIN observation o USING (observation_id)
        JOIN source_document sd USING (source_document_id)
        WHERE co.claim_id = :claim_id AND o.observation_id > :after_id
        ORDER BY o.observation_id LIMIT :limit
    """),
        {"claim_id": claim_id, "after_id": after_id, "limit": limit},
    ).mappings()
    return [dict(row) for row in rows]


def question_set(
    session: Session, context_id: int, window: str
) -> dict[str, Any] | None:
    row = (
        session.execute(
            sa.text("""
        SELECT qs.* FROM node_question_set qs JOIN model_task mt USING (model_task_id)
        WHERE qs.node_context_id = :context_id AND qs.time_window = :window
          AND mt.task_kind = 'FOLLOWUP_QUESTIONS' AND mt.status = 'SUCCESS'
          AND (SELECT count(*) FROM node_question_set sibling
               WHERE sibling.node_context_id = qs.node_context_id
                 AND sibling.model_task_id = qs.model_task_id
                 AND sibling.as_of_at = qs.as_of_at) = 2
    """),
            {"context_id": context_id, "window": window},
        )
        .mappings()
        .one_or_none()
    )
    return dict(row) if row else None


def questions(
    session: Session, set_id: int, after_order: int, limit: int
) -> list[dict[str, Any]]:
    rows = session.execute(
        sa.text("""
        SELECT * FROM node_question WHERE question_set_id = :set_id
          AND display_order > :after_order ORDER BY display_order LIMIT :limit
    """),
        {"set_id": set_id, "after_order": after_order, "limit": limit},
    ).mappings()
    return [dict(row) for row in rows]


def question(session: Session, question_id: int) -> dict[str, Any] | None:
    row = (
        session.execute(
            sa.text("""
        SELECT q.*, qs.node_context_id, qs.time_window, qs.as_of_at, nc.node_id
        FROM node_question q JOIN node_question_set qs USING (question_set_id)
        JOIN node_context nc USING (node_context_id) WHERE q.question_id = :id
    """),
            {"id": question_id},
        )
        .mappings()
        .one_or_none()
    )
    return dict(row) if row else None


def question_claims(session: Session, question_id: int) -> list[dict[str, Any]]:
    rows = session.execute(
        sa.text("""
        SELECT qc.*, c.statement_text FROM node_question_claim qc
        JOIN claim c USING (claim_id) WHERE question_id = :id ORDER BY display_order
    """),
        {"id": question_id},
    ).mappings()
    return [dict(row) for row in rows]


def valid_questions(
    session: Session,
    set_id: int,
    basis_ids: list[int],
    start_at: datetime,
    as_of_at: datetime,
) -> bool:
    return bool(
        session.scalar(
            sa.text("""
        SELECT NOT EXISTS (
          SELECT 1 FROM node_question q WHERE q.question_set_id = :set_id AND (
            NOT EXISTS (SELECT 1 FROM node_question_claim qc WHERE qc.question_id =
            q.question_id AND qc.role = 'KEY_CLAIM')
            OR NOT EXISTS (
              SELECT 1 FROM node_question_claim qc JOIN claim_observation co USING
              (claim_id)
              JOIN observation o USING (observation_id) JOIN source_document sd USING
              (source_document_id)
              WHERE qc.question_id = q.question_id AND sd.published_at >= :start_at
              AND sd.published_at < :as_of_at
            )
            OR EXISTS (
              SELECT 1 FROM node_question_claim qc WHERE qc.question_id =
              q.question_id AND (
                NOT (qc.claim_id = ANY(:basis_ids)) OR NOT EXISTS (
                  SELECT 1 FROM claim_observation co WHERE co.claim_id = qc.claim_id)
              )
            )
          )
        )
    """),
            {
                "set_id": set_id,
                "basis_ids": basis_ids,
                "start_at": start_at,
                "as_of_at": as_of_at,
            },
        )
    )


def report_window(
    session: Session, node_id: int, document_id: int, task_id: int, window: str
) -> dict[str, Any] | None:
    row = (
        session.execute(
            sa.text("""
        SELECT iw.* FROM node_insight_window iw
        LEFT JOIN node_insight ni ON ni.node_insight_id = iw.node_insight_id
        WHERE iw.node_id = :node_id
          AND (iw.node_insight_id IS NULL OR (
            ni.node_id = iw.node_id AND ni.model_task_id = iw.model_task_id
            AND ni.node_search_document_id = iw.node_search_document_id
            AND ni.time_window = iw.time_window AND ni.as_of_at = iw.as_of_at))
          AND iw.node_search_document_id = :document_id AND iw.model_task_id = :task_id
          AND iw.time_window = :window
          AND (SELECT count(*) FROM node_insight_window sibling
            WHERE sibling.node_id = iw.node_id AND sibling.node_search_document_id =
            iw.node_search_document_id
              AND sibling.model_task_id = iw.model_task_id AND sibling.as_of_at =
              iw.as_of_at) = 2
    """),
            {
                "node_id": node_id,
                "document_id": document_id,
                "task_id": task_id,
                "window": window,
            },
        )
        .mappings()
        .one_or_none()
    )
    return dict(row) if row else None


def sections(session: Session, report_id: int) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in session.execute(
            sa.text("""
        SELECT * FROM node_insight_section WHERE node_insight_id = :id ORDER BY
        display_order
    """),
            {"id": report_id},
        ).mappings()
    ]


def section_claims(session: Session, section_id: int) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in session.execute(
            sa.text("""
        SELECT sc.*, c.statement_text FROM node_insight_section_claim sc
        JOIN claim c USING (claim_id) WHERE section_id = :id ORDER BY display_order
    """),
            {"id": section_id},
        ).mappings()
    ]


def claim_counts(
    session: Session, claim_id: int, start_at: datetime, as_of_at: datetime
) -> dict[str, Any]:
    return dict(
        session.execute(
            sa.text("""
        SELECT c.statement_text, c.modality, ki.current_state,
          count(DISTINCT sd.evidence_group_id) FILTER (
            WHERE sd.published_at >= :start_at AND sd.published_at < :as_of_at
          )::integer AS evidence_group_count
        FROM claim c JOIN knowledge_item ki ON ki.knowledge_item_id = c.claim_id
        JOIN claim_observation co USING (claim_id) JOIN observation o USING
        (observation_id)
        JOIN source_document sd USING (source_document_id) WHERE c.claim_id = :id
        GROUP BY c.claim_id, ki.current_state
    """),
            {"id": claim_id, "start_at": start_at, "as_of_at": as_of_at},
        )
        .mappings()
        .one()
    )
