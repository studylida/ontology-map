"""Runtime inputs and prepared bindings for the #127 product worker.

These are not staging records. Approved ontology identities are read from the
DB; constants below only reject unapproved codes and representations.
"""

import json
import re
from dataclasses import dataclass
from hashlib import sha256
from struct import pack
from typing import Any

from ontology_map.extraction import ExtractionLimits
from ontology_map.extraction_contracts import ClaimProposal, Ontology, SourceSpan
from ontology_map.entity_resolution_contracts import Resolution

VALIDATOR_VERSION = "ke127-validator-v1"
PROMPT_VERSION = "knowledge-extraction-127-v1"

# #126 5612152332. This is an allowlist, never a database seed operation.
RELATIONS: dict[str, tuple[str, tuple[tuple[str, str], ...]]] = {
    "AFFILIATED_WITH": ("DIRECTED", (("PERSON", "COMPANY"),)),
    "DEVELOPS": ("DIRECTED", (("COMPANY", "TECHNOLOGY"), ("PERSON", "TECHNOLOGY"))),
    "COLLABORATES_WITH": ("SYMMETRIC", (("COMPANY", "COMPANY"),)),
    "ANNOUNCES": ("DIRECTED", tuple((s, t) for s in ("COMPANY", "PERSON") for t in ("TECHNOLOGY", "EVENT"))),
    "INVESTS_IN": ("DIRECTED", (("COMPANY", "COMPANY"), ("COMPANY", "TECHNOLOGY"))),
    "ADOPTS": ("DIRECTED", (("COMPANY", "TECHNOLOGY"),)),
    "TESTS": ("DIRECTED", (("COMPANY", "TECHNOLOGY"),)),
    "SUPPLIES": ("DIRECTED", (("COMPANY", "TECHNOLOGY"),)),
    "SUPPLIES_TO": ("DIRECTED", (("COMPANY", "COMPANY"),)),
    "INCLUDES": ("DIRECTED", (("TECHNOLOGY", "TECHNOLOGY"),)),
    "PARTICIPATES_IN": ("DIRECTED", (("COMPANY", "EVENT"), ("PERSON", "EVENT"))),
    "MENTIONS": ("DIRECTED", tuple((s, t) for s in ("COMPANY", "PERSON") for t in ("COMPANY", "PERSON", "TECHNOLOGY", "EVENT"))),
    "HAS_TOPIC": ("DIRECTED", tuple((s, "TOPIC") for s in ("COMPANY", "PERSON", "TECHNOLOGY", "EVENT"))),
}
ATTRIBUTES = {
    "ROLE_TITLE": ("PERSON", "STRING", None),
    "TECHNOLOGY_VERSION": ("TECHNOLOGY", "STRING", None),
    "COMMERCIALIZATION_STATUS": ("TECHNOLOGY", "STRING", None),
    "COMMERCIALIZATION_SCHEDULE": ("TECHNOLOGY", "STRING", None),
    "CORE_COUNT": ("TECHNOLOGY", "NUMBER", "COUNT"),
}
# No MAX_MEMORY_BANDWIDTH mapping: selecting or converting a unit is #126.


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def task_key(input_hash: bytes, model: str, schema_id: int) -> bytes:
    def frame(text: str) -> bytes:
        data = text.encode("utf-8")
        return pack(">Q", len(data)) + data
    return sha256(
        b"TASK1" + frame("KNOWLEDGE_EXTRACTION") + input_hash
        + pack(">q", schema_id) + frame(model) + frame(PROMPT_VERSION)
    ).digest()


@dataclass(frozen=True)
class WorkerOptions:
    limits: ExtractionLimits
    statement_language: str = "ko"
    include_structure: bool = True
    corrective_input: str | None = None
    execution_generation: str | None = None

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*", self.statement_language):
            raise ValueError("INVALID_STATEMENT_LANGUAGE")
        for value in (self.corrective_input, self.execution_generation):
            if value is not None and not value.strip():
                raise ValueError("EMPTY_CORRECTIVE_OR_GENERATION")


@dataclass(frozen=True)
class References:
    schema_id: int
    schema_version: int
    ontology: Ontology
    lint_policy_id: int
    evidence_rule_id: int
    # Safe diagnostic codes, not model payload or a fake active DB revision.
    unavailable: tuple[str, ...]


@dataclass(frozen=True)
class PreparedClaim:
    claim: ClaimProposal
    evidence: tuple[SourceSpan, ...]
    resolutions: tuple[Resolution, ...]
    existing_claim_id: int | None = None
    # Canonical persisted semantic snapshot, used only for reuse revalidation.
    existing_signature: bytes | None = None


@dataclass(frozen=True)
class WorkerResult:
    task_id: int
    status: str
    applied_claim_ids: tuple[int, ...] = ()
    excluded: tuple[tuple[str, str], ...] = ()
    unavailable: tuple[str, ...] = ()
