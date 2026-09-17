"""Runtime-only Claim semantic duplicate contract for #127.

This helper never owns a durable model_task or persists its input/output.
Code selects the candidate claim IDs; model output can only choose among them.
"""

from typing import Literal

from pydantic import Field, model_validator

from ontology_map.extraction_contracts import Contract, Modality, Text

CLAIM_DUPLICATE_PROMPT = """ontology-map의 기존 Claim 의미 중복 판정 역할이다.
입력의 새 Claim은 이미 자기 근거와 ontology 검증을 통과했다. 제공된 기존 Claim 후보와
새 Claim의 statement·modality·canonical semantic targets만 비교하라. 문장 표현이 달라도
주체·대상·관계·속성값·사건시간·계획/부정/조건을 포함한 같은 명제를 나타낼 때만 SAME이다.
일부 대상·수량·시점·modality가 다르면 NEW다. 자료만으로 구분할 수 없으면 UNRESOLVED다.
후보 statement를 새 Claim의 근거로 사용하거나 세계의 진실을 판정하지 마라. SAME일 때만
제공된 claim_id 하나를 그대로 반환하고, NEW/UNRESOLVED에는 claim_id를 반환하지 마라."""


class ClaimDuplicateCandidate(Contract):
    claim_id: int = Field(gt=0)
    statement: Text
    modality: Text
    semantic_targets: tuple[Text, ...]


class ClaimDuplicateInput(Contract):
    statement: Text
    modality: Modality
    semantic_targets: tuple[Text, ...]
    candidates: tuple[ClaimDuplicateCandidate, ...]


class ClaimDuplicateProposal(Contract):
    decision: Literal["SAME", "NEW", "UNRESOLVED"]
    claim_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_shape(self) -> "ClaimDuplicateProposal":
        if (self.decision == "SAME") != (self.claim_id is not None):
            raise ValueError("INVALID_CLAIM_DUPLICATE_DECISION_SHAPE")
        return self
