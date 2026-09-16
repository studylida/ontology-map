from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256

import sqlalchemy as sa
from sqlalchemy import Connection
from sqlalchemy.engine import RowMapping

from ontology_map.db.schema import evidence_group, source_document


class SourceMaterializationError(RuntimeError):
    """Base error for deterministic source-document persistence failures."""


class EvidenceGroupNotFound(SourceMaterializationError):
    """Raised when an approved Evidence Group is not present in the database."""


class EvidenceGroupConflict(SourceMaterializationError):
    """Raised when a source_key is already tied to a different Evidence Group."""


@dataclass(frozen=True)
class SourceDocumentInput:
    source_key: str
    canonical_url: str
    publisher_name: str
    title: str
    author_text: str | None
    original_language: str
    normalized_body: str
    body_hash: bytes
    published_at: datetime | None
    published_precision: str
    source_modified_at: datetime | None
    modified_precision: str


@dataclass(frozen=True)
class SourceDocumentWriteResult:
    source_document_id: int
    version_no: int
    created: bool


def _source_lock_key(source_key: str) -> int:
    raw = sha256(source_key.encode("utf-8")).digest()[:8]
    return int.from_bytes(raw, byteorder="big", signed=True)


def _same_immutable_document(
    row: RowMapping, document: SourceDocumentInput
) -> bool:
    return (
        str(row["canonical_url"]) == document.canonical_url
        and str(row["publisher_name"]) == document.publisher_name
        and str(row["title"]) == document.title
        and row["author_text"] == document.author_text
        and str(row["original_language"]) == document.original_language
        and str(row["normalized_body"]) == document.normalized_body
        and bytes(row["body_hash"]) == document.body_hash
        and row["published_at"] == document.published_at
        and str(row["published_precision"]) == document.published_precision
        and row["source_modified_at"] == document.source_modified_at
        and str(row["modified_precision"]) == document.modified_precision
    )


def materialize_source_document(
    connection: Connection,
    *,
    document: SourceDocumentInput,
    evidence_group_id: int,
    checked_at: datetime,
) -> SourceDocumentWriteResult:
    """Persist one already-qualified and lineage-approved immutable document version."""

    connection.execute(
        sa.select(sa.func.pg_advisory_xact_lock(_source_lock_key(document.source_key)))
    )

    group_exists = connection.execute(
        sa.select(evidence_group.c.evidence_group_id).where(
            evidence_group.c.evidence_group_id == evidence_group_id
        )
    ).scalar_one_or_none()
    if group_exists is None:
        raise EvidenceGroupNotFound("approved evidence_group_id does not exist")

    latest = (
        connection.execute(
            sa.select(source_document)
            .where(source_document.c.source_key == document.source_key)
            .order_by(source_document.c.version_no.desc())
            .limit(1)
            .with_for_update()
        )
        .mappings()
        .one_or_none()
    )
    if latest is not None:
        if int(latest["evidence_group_id"]) != evidence_group_id:
            raise EvidenceGroupConflict(
                "source_key is already assigned to another evidence_group_id"
            )
        if _same_immutable_document(latest, document):
            source_document_id = int(latest["source_document_id"])
            connection.execute(
                source_document.update()
                .where(source_document.c.source_document_id == source_document_id)
                .values(last_checked_at=checked_at, last_check_status="SUCCESS")
            )
            return SourceDocumentWriteResult(
                source_document_id=source_document_id,
                version_no=int(latest["version_no"]),
                created=False,
            )
        version_no = int(latest["version_no"]) + 1
    else:
        version_no = 1

    source_document_id = int(
        connection.execute(
            source_document.insert()
            .values(
                evidence_group_id=evidence_group_id,
                source_key=document.source_key,
                version_no=version_no,
                canonical_url=document.canonical_url,
                publisher_name=document.publisher_name,
                title=document.title,
                author_text=document.author_text,
                original_language=document.original_language,
                normalized_body=document.normalized_body,
                body_hash=document.body_hash,
                published_at=document.published_at,
                published_precision=document.published_precision,
                source_modified_at=document.source_modified_at,
                modified_precision=document.modified_precision,
                last_checked_at=checked_at,
                last_check_status="SUCCESS",
            )
            .returning(source_document.c.source_document_id)
        ).scalar_one()
    )
    return SourceDocumentWriteResult(
        source_document_id=source_document_id,
        version_no=version_no,
        created=True,
    )
