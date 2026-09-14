from datetime import UTC, datetime

from ontology_map import followup_generation as service
from ontology_map.followup_generation_contracts import (
    ClaimConnection,
    EvidenceExcerpt,
    FollowupAgentInput,
    FollowupClaimReference,
    FollowupQuestionCandidate,
    FollowupQuestionsProposal,
    GroundedClaim,
    PreparedFollowup,
)


def test_one_sentence_answer_is_not_dropped_by_deterministic_validation() -> None:
    as_of = datetime(2026, 9, 14, 0, 0, tzinfo=UTC)
    grounded = GroundedClaim(
        claim_id=1,
        statement_text="검증된 주장",
        modality="FACT",
        period_role="IN_WINDOW",
        connections=(ClaimConnection(kind="ATTRIBUTE", label="시험 속성"),),
        evidence=(
            EvidenceExcerpt(
                observation_id=1,
                source_document_id=1,
                evidence_group_id=1,
                publisher_name="시험 발행처",
                title="시험 문서",
                quote_text="검증된 원문",
                published_at=as_of,
                period_role="IN_WINDOW",
            ),
        ),
    )
    prepared = PreparedFollowup(
        promotion_batch_id=1,
        node_context_id=1,
        node_search_document_id=1,
        basis_ids=(1,),
        agent_input=FollowupAgentInput(
            node_id=1,
            node_type="COMPANY",
            preferred_alias="가온",
            time_window="RECENT_90_DAYS",
            as_of_at=as_of,
            claims=(grounded,),
        ),
    )
    proposal = FollowupQuestionsProposal(
        questions=(
            FollowupQuestionCandidate(
                display_order=1,
                question_text="무엇을 확인할 수 있나요?",
                answer_text="현재 공개 근거에서 이 사실을 확인할 수 있습니다.",
                claims=(
                    FollowupClaimReference(
                        claim_id=1,
                        role="KEY_CLAIM",
                        display_order=1,
                    ),
                ),
            ),
        )
    )

    result = service.validate_proposal(prepared, proposal)
    assert len(result.candidates) == 1
    assert result.failures == ()
