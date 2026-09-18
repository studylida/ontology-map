"""Small product DTO fixtures; no real corpus or quality claims."""

from ontology_map.claim_duplicate import ClaimDuplicateProposal
from ontology_map.entity_resolution_contracts import ResolutionProposal
from ontology_map.extraction_contracts import (
    BodySelection,
    ClaimSupport,
    KnowledgeProposals,
    MeaningSupport,
)
from ontology_map.followup_generation_contracts import FollowupQuestionsProposal
from ontology_map.insight_generation_contracts import InsightBundleProposal
from ontology_map.node_context_generation_contracts import NodeContextProposal

CASES = {
    "body": (BodySelection, {"source_ids": []}),
    "generation": (KnowledgeProposals, {"claims": []}),
    "claim_support": (ClaimSupport, {"verdict": "UNRESOLVED"}),
    "meaning_support": (MeaningSupport, {"verdict": "UNRESOLVED"}),
    "entity_resolution": (
        ResolutionProposal,
        {"decision": "UNRESOLVED", "node_id": None},
    ),
    "claim_duplicate": (
        ClaimDuplicateProposal,
        {"decision": "UNRESOLVED", "claim_id": None},
    ),
    "node_context": (NodeContextProposal, {"context_text": "합성 맥락"}),
    "followup": (FollowupQuestionsProposal, {"questions": []}),
    "insight": (
        InsightBundleProposal,
        {
            "recent_90_days": {"report": None},
            "recent_1_year": {"report": None},
        },
    ),
}
