from datetime import UTC, datetime

import sqlalchemy as sa
from test_relations import rollback_session

from ontology_map.db import followup_generation as db
from ontology_map.db import panel as panel_queries
from ontology_map.db import schema as s
from ontology_map.db.panel_fixture import load_panel_fixture
from ontology_map.exploration import TimeWindow


def _insert_event_conflict(
    session,
    *,
    event_node_id: int,
    claim_ids: tuple[int, int],
) -> int:
    conflict_id = session.scalar(
        s.conflict_set.insert()
        .values(
            event_node_id=event_node_id,
            modality="FACT",
            current_state="AGENT_PROPOSED",
        )
        .returning(s.conflict_set.c.conflict_set_id)
    )
    assert conflict_id is not None
    session.execute(
        s.conflict_member.insert(),
        [
            {
                "conflict_set_id": conflict_id,
                "claim_id": claim_ids[0],
                "position_key": "A",
            },
            {
                "conflict_set_id": conflict_id,
                "claim_id": claim_ids[1],
                "position_key": "B",
            },
        ],
    )
    return int(conflict_id)


def test_prepare_followup_only_exposes_conflicts_for_center_node_scope() -> None:
    _, ids = load_panel_fixture()
    with rollback_session() as session:
        context = panel_queries.context(session, ids["gaon"])
        assert context is not None
        context_id = int(context["node_context_id"])
        now = datetime.now(UTC)
        initial = db.prepare_followup(
            session,
            context_id,
            TimeWindow.RECENT_90_DAYS,
            now,
        )
        claim_ids = tuple(item.claim_id for item in initial.agent_input.claims[:2])
        assert len(claim_ids) == 2

        other_node_id = session.scalar(
            sa.select(s.node.c.node_id)
            .where(s.node.c.node_id != ids["gaon"])
            .order_by(s.node.c.node_id)
            .limit(1)
        )
        assert other_node_id is not None

        out_of_scope_id = _insert_event_conflict(
            session,
            event_node_id=int(other_node_id),
            claim_ids=(claim_ids[0], claim_ids[1]),
        )
        in_scope_id = _insert_event_conflict(
            session,
            event_node_id=ids["gaon"],
            claim_ids=(claim_ids[0], claim_ids[1]),
        )

        prepared = db.prepare_followup(
            session,
            context_id,
            TimeWindow.RECENT_90_DAYS,
            now,
        )
        visible = {pair.conflict_set_id for pair in prepared.agent_input.conflict_pairs}
        assert in_scope_id in visible
        assert out_of_scope_id not in visible
