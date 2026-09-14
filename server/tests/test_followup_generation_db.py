from datetime import UTC, datetime, timedelta
from hashlib import sha256

import sqlalchemy as sa
from test_relations import rollback_session

from ontology_map import followup_generation as service
from ontology_map.db import followup_generation as db
from ontology_map.db import panel as panel_queries
from ontology_map.db import schema as s
from ontology_map.db.panel_fixture import load_panel_fixture
from ontology_map.exploration import TimeWindow
from ontology_map.followup_generation_contracts import (
    FollowupClaimReference,
    FollowupQuestionCandidate,
    FollowupQuestionsProposal,
)


def _clear_question_sets(session, context_id: int) -> None:
    set_ids = sa.select(s.node_question_set.c.question_set_id).where(
        s.node_question_set.c.node_context_id == context_id
    )
    question_ids = sa.select(s.node_question.c.question_id).where(
        s.node_question.c.question_set_id.in_(set_ids)
    )
    session.execute(
        s.node_question_claim.delete().where(
            s.node_question_claim.c.question_id.in_(question_ids)
        )
    )
    session.execute(
        s.node_question.delete().where(s.node_question.c.question_set_id.in_(set_ids))
    )
    session.execute(
        s.node_question_set.delete().where(
            s.node_question_set.c.node_context_id == context_id
        )
    )


def _running_task(session, seed: bytes, now: datetime) -> int:
    version = (
        session.scalar(
            sa.select(sa.func.max(s.output_schema_definition.c.version_no)).where(
                s.output_schema_definition.c.task_kind == "FOLLOWUP_QUESTIONS"
            )
        )
        or 0
    ) + 1
    contract_id = session.scalar(
        s.output_schema_definition.insert()
        .values(
            task_kind="FOLLOWUP_QUESTIONS",
            version_no=version,
            schema_json=service.output_schema(),
            is_active=False,
        )
        .returning(s.output_schema_definition.c.output_schema_definition_id)
    )
    assert contract_id is not None
    task_id = session.scalar(
        s.model_task.insert()
        .values(
            task_kind="FOLLOWUP_QUESTIONS",
            input_hash=sha256(seed + b":input").digest(),
            output_schema_definition_id=contract_id,
            model_version=service.MODEL_VERSION,
            prompt_version=service.PROMPT_VERSION,
            cache_key=sha256(seed + b":cache").digest(),
            status="RUNNING",
            attempt_count=1,
            lease_owner="followup-test-worker",
            lease_expires_at=now + timedelta(minutes=10),
        )
        .returning(s.model_task.c.model_task_id)
    )
    assert task_id is not None
    session.execute(
        s.agent_attempt.insert().values(
            model_task_id=task_id,
            attempt_no=1,
            outcome="SUCCESS",
            attempted_at=now,
        )
    )
    return int(task_id)


def _fixture_snapshot(session):
    _, ids = load_panel_fixture()
    context = panel_queries.context(session, ids["gaon"])
    assert context is not None
    context_id = int(context["node_context_id"])
    _clear_question_sets(session, context_id)
    now = datetime.now(UTC)
    prepared = db.prepare_followup(
        session,
        context_id,
        TimeWindow.RECENT_90_DAYS,
        now,
    )
    assert prepared.agent_input.claims
    return context_id, prepared, now


def _ordinary_in_window_claim(prepared) -> int:
    conflict_claims = {
        claim_id
        for pair in prepared.agent_input.conflict_pairs
        for claim_id in pair.claim_ids
    }
    return next(
        item.claim_id
        for item in prepared.agent_input.claims
        if item.period_role == "IN_WINDOW" and item.claim_id not in conflict_claims
    )


def test_apply_followup_persists_valid_partial_result_and_task_success() -> None:
    _, ids = load_panel_fixture()
    with rollback_session() as session:
        context = panel_queries.context(session, ids["gaon"])
        assert context is not None
        context_id = int(context["node_context_id"])
        _clear_question_sets(session, context_id)
        now = datetime.now(UTC)
        prepared = db.prepare_followup(
            session, context_id, TimeWindow.RECENT_90_DAYS, now
        )
        claim_id = _ordinary_in_window_claim(prepared)
        task_id = _running_task(session, b"valid", now)
        proposal = FollowupQuestionsProposal(
            questions=(
                FollowupQuestionCandidate(
                    display_order=1,
                    question_text="현재 자료에서 직접 확인되는 역할은 무엇인가요?",
                    answer_text=(
                        "현재 자료에서는 공동 사업과 연결된 역할을 확인할 수 있습니다. "
                        "제공된 근거만으로 그 범위를 넘어선 "
                        "성과까지 판단할 수는 없습니다."
                    ),
                    claims=(
                        FollowupClaimReference(
                            claim_id=claim_id,
                            role="KEY_CLAIM",
                            display_order=1,
                        ),
                    ),
                ),
                FollowupQuestionCandidate(
                    display_order=2,
                    question_text="검증되지 않은 Claim으로도 답할 수 있나요?",
                    answer_text=(
                        "검증되지 않은 근거는 사용할 수 없습니다. "
                        "이 후보는 전체 질문 단위로 제외되어야 합니다."
                    ),
                    claims=(
                        FollowupClaimReference(
                            claim_id=9223372036854775807,
                            role="KEY_CLAIM",
                            display_order=1,
                        ),
                    ),
                ),
            )
        )

        result = db.apply_followup(
            session,
            model_task_id=task_id,
            prepared=prepared,
            proposal=proposal,
            finished_at=now + timedelta(seconds=1),
        )
        assert result.status == "SUCCESS"
        assert result.stored_count == 1
        task = (
            session.execute(
                sa.select(s.model_task).where(s.model_task.c.model_task_id == task_id)
            )
            .mappings()
            .one()
        )
        assert task["status"] == "SUCCESS"
        assert task["lease_owner"] is None
        questions = (
            session.execute(
                sa.select(s.node_question).where(
                    s.node_question.c.question_set_id == result.question_set_id
                )
            )
            .mappings()
            .all()
        )
        assert len(questions) == 1
        assert questions[0]["section_id"] is None


def test_apply_followup_persists_normal_empty_as_success() -> None:
    _, ids = load_panel_fixture()
    with rollback_session() as session:
        context = panel_queries.context(session, ids["gaon"])
        assert context is not None
        context_id = int(context["node_context_id"])
        _clear_question_sets(session, context_id)
        now = datetime.now(UTC)
        prepared = db.prepare_followup(
            session, context_id, TimeWindow.RECENT_1_YEAR, now
        )
        task_id = _running_task(session, b"empty", now)
        result = db.apply_followup(
            session,
            model_task_id=task_id,
            prepared=prepared,
            proposal=FollowupQuestionsProposal(questions=()),
            finished_at=now + timedelta(seconds=1),
        )
        assert result.status == "SUCCESS"
        assert result.stored_count == 0
        assert result.question_set_id is not None
        count = session.scalar(
            sa.select(sa.func.count())
            .select_from(s.node_question)
            .where(s.node_question.c.question_set_id == result.question_set_id)
        )
        assert count == 0


def test_apply_followup_blocks_stale_basis_without_writing_result() -> None:
    _, ids = load_panel_fixture()
    with rollback_session() as session:
        context = panel_queries.context(session, ids["gaon"])
        assert context is not None
        context_id = int(context["node_context_id"])
        _clear_question_sets(session, context_id)
        now = datetime.now(UTC)
        prepared = db.prepare_followup(
            session, context_id, TimeWindow.RECENT_90_DAYS, now
        )
        claim_id = prepared.agent_input.claims[0].claim_id
        task_id = _running_task(session, b"stale", now)
        session.execute(
            s.knowledge_item.update()
            .where(s.knowledge_item.c.knowledge_item_id == claim_id)
            .values(current_state="ON_HOLD")
        )
        result = db.apply_followup(
            session,
            model_task_id=task_id,
            prepared=prepared,
            proposal=FollowupQuestionsProposal(questions=()),
            finished_at=now + timedelta(seconds=1),
        )
        assert result.status == "VALIDATION_BLOCKED"
        assert result.reason == "STALE_INPUT"
        assert result.question_set_id is None
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(s.node_question_set)
                .where(s.node_question_set.c.model_task_id == task_id)
            )
            == 0
        )
