from dataclasses import dataclass, field
from enum import StrEnum
from unicodedata import normalize

from sqlalchemy.orm import Session

from ontology_map.db.search import (
    SearchNodeRow,
    list_exact_alias_matches,
    list_full_text_matches,
)
from ontology_map.exploration import NodeType

MAX_SEARCH_LIMIT = 20
FULL_TEXT_CANDIDATE_LIMIT = 50


class InvalidSearchQueryError(Exception):
    pass


class MatchReason(StrEnum):
    EXACT_ALIAS = "EXACT_ALIAS"
    FULL_TEXT = "FULL_TEXT"


@dataclass(frozen=True)
class SearchNode:
    node_id: int
    name: str
    node_type: NodeType


@dataclass(frozen=True)
class SearchResult:
    node: SearchNode
    match_reasons: tuple[MatchReason, ...]


@dataclass
class _Candidate:
    row: SearchNodeRow
    match_reasons: list[MatchReason] = field(default_factory=list)


def search_nodes(session: Session, query: str, limit: int = 5) -> list[SearchResult]:
    normalized_query = normalize("NFC", query).strip()
    if not normalized_query or not 1 <= limit <= MAX_SEARCH_LIMIT:
        raise InvalidSearchQueryError

    candidates: dict[int, _Candidate] = {}
    ordered_ids: list[int] = []
    branches = (
        (
            MatchReason.EXACT_ALIAS,
            list_exact_alias_matches(session, normalized_query, limit),
        ),
        (
            MatchReason.FULL_TEXT,
            list_full_text_matches(
                session, normalized_query, FULL_TEXT_CANDIDATE_LIMIT
            ),
        ),
    )
    for reason, rows in branches:
        for row in rows:
            if row.node_id not in candidates:
                candidates[row.node_id] = _Candidate(row=row)
                ordered_ids.append(row.node_id)
            candidates[row.node_id].match_reasons.append(reason)

    results: list[SearchResult] = []
    for node_id in ordered_ids[:limit]:
        candidate = candidates[node_id]
        results.append(
            SearchResult(
                node=SearchNode(
                    node_id=candidate.row.node_id,
                    name=candidate.row.name,
                    node_type=NodeType(
                        code=candidate.row.node_type_code,
                        display_name=candidate.row.node_type_display_name,
                    ),
                ),
                match_reasons=tuple(candidate.match_reasons),
            )
        )
    return results
