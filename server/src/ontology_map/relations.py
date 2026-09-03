from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from ontology_map.db import relations as relation_queries
from ontology_map.db.exploration import is_public_node
from ontology_map.exploration import NodeType, PublicationNotReadyError
from ontology_map.pagination import InvalidCursorError, decode_cursor, encode_cursor

_NODE_RELATIONS_CURSOR = "node-relations"
_RELATION_EVIDENCE_CURSOR = "relation-evidence"


class NodeRelationsNotFoundError(Exception):
    pass


class RelationEvidenceNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class RelatedNode:
    node_id: int
    name: str
    node_type: NodeType


@dataclass(frozen=True)
class NodeRelation:
    relation_id: int
    other_node: RelatedNode
    relation_type_display_name: str
    supporting_evidence_group_count: int
    has_conflict: bool


@dataclass(frozen=True)
class NodeRelationsPage:
    items: list[NodeRelation]
    next_cursor: str | None


@dataclass(frozen=True)
class EvidenceSource:
    title: str
    publisher_name: str
    published_at: datetime | None
    published_precision: str
    canonical_url: str


@dataclass(frozen=True)
class EvidenceLocator:
    paragraph_number: int | None
    start_char: int
    end_char: int


@dataclass(frozen=True)
class RelationEvidence:
    claim_text: str
    stance: str
    source: EvidenceSource
    quote_text: str
    locator: EvidenceLocator


@dataclass(frozen=True)
class RelationEvidencePage:
    items: list[RelationEvidence]
    trace_count: int
    next_cursor: str | None


def _positive_integer(value: object) -> int:
    if type(value) is not int or value < 1:
        raise InvalidCursorError
    return value


def _node_relations_position(
    cursor: str | None, node_id: int
) -> tuple[int | None, int | None]:
    if cursor is None:
        return None, None
    values = decode_cursor(
        cursor,
        kind=_NODE_RELATIONS_CURSOR,
        scope={"node_id": node_id},
    )
    if len(values) != 2:
        raise InvalidCursorError
    return _positive_integer(values[0]), _positive_integer(values[1])


def list_node_relations(
    session: Session,
    node_id: int,
    *,
    cursor: str | None,
    limit: int,
) -> NodeRelationsPage:
    after_support_count, after_relation_id = _node_relations_position(cursor, node_id)
    if not is_public_node(session, node_id):
        raise NodeRelationsNotFoundError
    search_document_id = relation_queries.get_public_search_document_id(
        session, node_id
    )
    if search_document_id is None:
        raise PublicationNotReadyError

    rows = relation_queries.list_node_relations(
        session,
        node_id=node_id,
        search_document_id=search_document_id,
        after_support_count=after_support_count,
        after_relation_id=after_relation_id,
        limit=limit + 1,
    )
    page_rows = rows[:limit]
    next_cursor = None
    if len(rows) > limit:
        last = page_rows[-1]
        next_cursor = encode_cursor(
            _NODE_RELATIONS_CURSOR,
            {"node_id": node_id},
            [last.supporting_evidence_group_count, last.relation_id],
        )
    return NodeRelationsPage(
        items=[
            NodeRelation(
                relation_id=row.relation_id,
                other_node=RelatedNode(
                    node_id=row.other_node_id,
                    name=row.other_name,
                    node_type=NodeType(
                        code=row.other_node_type_code,
                        display_name=row.other_node_type_display_name,
                    ),
                ),
                relation_type_display_name=row.relation_type_display_name,
                supporting_evidence_group_count=(row.supporting_evidence_group_count),
                has_conflict=row.has_conflict,
            )
            for row in page_rows
        ],
        next_cursor=next_cursor,
    )


def _evidence_position(
    cursor: str | None, relation_id: int
) -> tuple[datetime | None, int | None, int | None, int | None]:
    if cursor is None:
        return None, None, None, None
    values = decode_cursor(
        cursor,
        kind=_RELATION_EVIDENCE_CURSOR,
        scope={"relation_id": relation_id},
    )
    if len(values) != 4 or (values[0] is not None and type(values[0]) is not str):
        raise InvalidCursorError
    published_at = None
    if values[0] is not None:
        try:
            published_at = datetime.fromisoformat(values[0])
        except ValueError as error:
            raise InvalidCursorError from error
        if published_at.tzinfo is None or published_at.utcoffset() is None:
            raise InvalidCursorError
    return (
        published_at,
        _positive_integer(values[1]),
        _positive_integer(values[2]),
        _positive_integer(values[3]),
    )


def _trace_cursor(relation_id: int, row: relation_queries.EvidenceTraceRow) -> str:
    return encode_cursor(
        _RELATION_EVIDENCE_CURSOR,
        {"relation_id": relation_id},
        [
            row.published_at.isoformat() if row.published_at is not None else None,
            row.source_document_id,
            row.observation_id,
            row.claim_id,
        ],
    )


def list_relation_evidence(
    session: Session,
    relation_id: int,
    *,
    cursor: str | None,
    limit: int,
) -> RelationEvidencePage:
    position = _evidence_position(cursor, relation_id)
    counts = relation_queries.get_relation_evidence_counts(session, relation_id)
    if not counts.has_support:
        raise RelationEvidenceNotFoundError

    rows = relation_queries.list_relation_evidence(
        session,
        relation_id=relation_id,
        after_published_at=position[0],
        after_source_document_id=position[1],
        after_observation_id=position[2],
        after_claim_id=position[3],
        limit=limit + 1,
    )
    page_rows = rows[:limit]
    return RelationEvidencePage(
        items=[
            RelationEvidence(
                claim_text=row.claim_text,
                stance=row.stance,
                source=EvidenceSource(
                    title=row.source_title,
                    publisher_name=row.publisher_name,
                    published_at=row.published_at,
                    published_precision=row.published_precision,
                    canonical_url=row.canonical_url,
                ),
                quote_text=row.quote_text,
                locator=EvidenceLocator(
                    paragraph_number=row.paragraph_number,
                    start_char=row.start_char,
                    end_char=row.end_char,
                ),
            )
            for row in page_rows
        ],
        trace_count=counts.trace_count,
        next_cursor=(
            _trace_cursor(relation_id, page_rows[-1]) if len(rows) > limit else None
        ),
    )
