from dataclasses import dataclass
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class SearchNodeRow:
    node_id: int
    name: str
    node_type_code: str
    node_type_display_name: str


_SEARCHABLE_NODES_CTE = """
WITH RECURSIVE ranked_ready AS (
    SELECT
        pan.node_id,
        pan.node_search_document_id,
        row_number() OVER (
            PARTITION BY pan.node_id
            ORDER BY pb.ready_at DESC, pb.promotion_batch_id DESC
        ) AS ready_rank
    FROM publication_affected_node AS pan
    JOIN promotion_batch AS pb
      ON pb.promotion_batch_id = pan.promotion_batch_id
    WHERE pb.promotion_status = 'COMMITTED'
      AND pb.publication_status = 'READY'
      AND pan.node_search_document_id IS NOT NULL
),
searchable_nodes AS (
    SELECT
        n.node_id,
        rr.node_search_document_id,
        na.alias_text AS name,
        nt.node_type_code,
        nt.display_name AS node_type_display_name
    FROM ranked_ready AS rr
    JOIN node AS n ON n.node_id = rr.node_id
    JOIN knowledge_item AS nki ON nki.knowledge_item_id = n.node_id
    JOIN node_alias AS na ON na.node_id = n.node_id AND na.is_preferred
    JOIN node_type AS nt ON nt.node_type_id = n.node_type_id
    WHERE rr.ready_rank = 1
      AND nki.item_kind = 'NODE'
      AND nki.current_state IN ('EVIDENCE_VERIFIED', 'HUMAN_VERIFIED')
      AND NOT EXISTS (
          SELECT 1
          FROM node_merge AS nm
          WHERE nm.source_node_id = n.node_id
            AND nm.reversed_at IS NULL
      )
      AND NOT EXISTS (
          SELECT 1
          FROM lint_finding AS lf
          JOIN lint_policy_rule AS lpr
            ON lpr.lint_policy_rule_id = lf.lint_policy_rule_id
          WHERE lf.knowledge_item_id = n.node_id
            AND lf.resolved_at IS NULL
            AND lpr.severity = 'BLOCKING'
      )
      AND NOT EXISTS (
          SELECT 1
          FROM search_document_basis AS sdb
          JOIN knowledge_item AS bki
            ON bki.knowledge_item_id = sdb.knowledge_item_id
          WHERE sdb.node_search_document_id = rr.node_search_document_id
            AND (
                bki.current_state NOT IN (
                    'EVIDENCE_VERIFIED', 'HUMAN_VERIFIED'
                )
                OR EXISTS (
                    SELECT 1
                    FROM lint_finding AS blf
                    JOIN lint_policy_rule AS blpr
                      ON blpr.lint_policy_rule_id = blf.lint_policy_rule_id
                    WHERE blf.knowledge_item_id = bki.knowledge_item_id
                      AND blf.resolved_at IS NULL
                      AND blpr.severity = 'BLOCKING'
                )
            )
      )
)
"""

_SEARCH_VECTOR_EXPRESSION = """
(
    setweight(to_tsvector('simple', identity_text), 'A')
    ||
    setweight(to_tsvector('simple', knowledge_text), 'B')
)
"""


def _rows(result: sa.Result[Any]) -> list[SearchNodeRow]:
    return [
        SearchNodeRow(
            node_id=int(row["node_id"]),
            name=str(row["name"]),
            node_type_code=str(row["node_type_code"]),
            node_type_display_name=str(row["node_type_display_name"]),
        )
        for row in result.mappings()
    ]


def list_exact_alias_matches(
    session: Session, query: str, limit: int
) -> list[SearchNodeRow]:
    statement = sa.text(
        _SEARCHABLE_NODES_CTE
        + """
        , matched_alias_nodes AS (
            SELECT DISTINCT na.node_id
            FROM node_alias AS na
            WHERE na.alias_text = :query
        ),
        node_resolution(source_node_id, current_node_id) AS (
            SELECT node_id, node_id
            FROM matched_alias_nodes

            UNION ALL

            SELECT nr.source_node_id, nm.canonical_node_id
            FROM node_resolution AS nr
            JOIN node_merge AS nm
              ON nm.source_node_id = nr.current_node_id
             AND nm.reversed_at IS NULL
        ),
        canonical_matches AS (
            SELECT DISTINCT nr.current_node_id AS node_id
            FROM node_resolution AS nr
            WHERE NOT EXISTS (
                SELECT 1
                FROM node_merge AS nm
                WHERE nm.source_node_id = nr.current_node_id
                  AND nm.reversed_at IS NULL
            )
        )
        SELECT
            sn.node_id,
            sn.name,
            sn.node_type_code,
            sn.node_type_display_name
        FROM canonical_matches AS cm
        JOIN searchable_nodes AS sn ON sn.node_id = cm.node_id
        ORDER BY sn.node_id ASC
        LIMIT :limit
        """
    )
    return _rows(session.execute(statement, {"query": query, "limit": limit}))


def list_full_text_matches(
    session: Session, query: str, limit: int
) -> list[SearchNodeRow]:
    statement = sa.text(
        _SEARCHABLE_NODES_CTE
        + f"""
        , search_query AS (
            SELECT websearch_to_tsquery('simple', :query) AS value
        )
        SELECT
            sn.node_id,
            sn.name,
            sn.node_type_code,
            sn.node_type_display_name
        FROM searchable_nodes AS sn
        JOIN node_search_document AS nsd
          ON nsd.node_search_document_id = sn.node_search_document_id
         AND nsd.node_id = sn.node_id
        CROSS JOIN search_query AS sq
        WHERE {_SEARCH_VECTOR_EXPRESSION} @@ sq.value
        ORDER BY
            ts_rank_cd({_SEARCH_VECTOR_EXPRESSION}, sq.value) DESC,
            sn.node_id ASC
        LIMIT :limit
        """
    )
    return _rows(session.execute(statement, {"query": query, "limit": limit}))
