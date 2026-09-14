"""Minimal synchronous durable KNOWLEDGE_EXTRACTION product worker.

No scheduler, publication, runtime payload persistence, or provider auto-retry.
The caller supplies the existing ModelStudio instance and explicit run options.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import cast

import sqlalchemy as sa
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from ontology_map import extraction
from ontology_map.db import extraction_input as inputs
from ontology_map.db import extraction_promotion as storage
from ontology_map.db import model_tasks as tasks
from ontology_map.db import schema as db
from ontology_map.extraction_contracts import KnowledgeProposals, SourceSpan
from ontology_map.knowledge_extraction_contracts import References, WorkerOptions, WorkerResult
from ontology_map.knowledge_reconciliation import reconcile
from ontology_map.model_studio import CallFailed, ModelStudio


@contextmanager
def _read(engine: Engine) -> Iterator[Session]:
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn:
        with conn.begin():
            conn.execute(sa.text("SET TRANSACTION READ ONLY"))
            with Session(bind=conn) as session:
                yield session


def enqueue(engine: Engine, document_id: int, options: WorkerOptions, *, manual_from_task_id: int | None = None) -> int:
    with Session(engine) as session, session.begin():
        if options.execution_generation is not None:
            if manual_from_task_id is None:
                raise ValueError("MANUAL_REPROCESS_REQUIRES_FAILED_TASK")
            previous = session.execute(sa.select(db.model_task).where(db.model_task.c.model_task_id == manual_from_task_id)).mappings().one()
            if previous["status"] != "FINAL_FAILED" or previous["source_document_id"] != document_id:
                raise ValueError("MANUAL_REPROCESS_REQUIRES_FAILED_TASK")
        elif manual_from_task_id is not None:
            raise ValueError("MANUAL_REPROCESS_REQUIRES_NEW_GENERATION")
        return inputs.enqueue(session, document_id, options)


def _status(engine: Engine, task_id: int) -> str:
    with Session(engine) as session:
        return str(session.execute(sa.select(db.model_task.c.status).where(db.model_task.c.model_task_id == task_id)).scalar_one())


def _generation(
    engine: Engine, lease: tasks.Lease, body: list[SourceSpan], refs: References,
    models: ModelStudio, options: WorkerOptions,
) -> KnowledgeProposals | None:
    slot: tasks.CallSlot | None = None
    attempted_at: datetime | None = None

    def reserve_before_wire() -> None:
        nonlocal slot, attempted_at
        with Session(engine) as session, session.begin():
            slot = tasks.reserve_slot(session, lease)
        if slot is None:
            raise tasks.LeaseLost("CALL_BUDGET_EXHAUSTED")
        attempted_at = datetime.now(UTC)

    try:
        result = extraction.generate_knowledge(
            body, refs.ontology, models, options.limits,
            include_structure=options.include_structure,
            statement_language=options.statement_language,
            corrective_input=options.corrective_input,
            before_send=reserve_before_wire,
        )
        ids = [c.candidate_id for c in result.claims]
        if len(ids) != len(set(ids)) or len(ids) > options.limits.max_candidates:
            raise CallFailed("OUTPUT_CONTRACT_ERROR", fatal=False)
    except CallFailed as error:
        if slot is None:
            with Session(engine) as session, session.begin():
                tasks.fail_execution(session, lease, transient=False)
            raise
        if error.code not in tasks.OUTCOMES or error.code == "SUCCESS":
            # Unknown transmission/results consume the slot; reclaim owns UNKNOWN.
            return None
        with Session(engine) as session, session.begin():
            tasks.record_terminal(session, slot, tasks.TerminalResult(
                cast(tasks.Outcome, error.code), cast(datetime, attempted_at), error.code,
                transient=error.transient, retry_after=error.retry_after,
            ))
        return None
    if slot is None or attempted_at is None:
        raise ValueError("PRODUCT_PROVIDER_DID_NOT_RESERVE_SLOT")
    with Session(engine) as session, session.begin():
        tasks.record_terminal(session, slot, tasks.TerminalResult("SUCCESS", attempted_at))
    return result


def _finish_empty(engine: Engine, lease: tasks.Lease, *, valid: bool) -> str:
    with Session(engine) as session, session.begin():
        return tasks.finish_product(session, lease, valid=valid)


def _db_transient(error: sa.exc.DBAPIError) -> bool:
    code = str(getattr(error.orig, "sqlstate", ""))
    return bool(error.connection_invalidated or code in {"40001", "40P01", "55P03", "57P01"} or code.startswith("08"))


def _fail(engine: Engine, lease: tasks.Lease, transient: bool) -> None:
    # Unknown send reservations must survive; no result is fabricated here.
    try:
        with Session(engine) as session, session.begin():
            tasks.fail_execution(session, lease, transient=transient)
    except (tasks.LeaseLost, tasks.SlotBusy):
        return


def run_task(engine: Engine, task_id: int, models: ModelStudio, options: WorkerOptions, *, worker_name: str = "ke127") -> WorkerResult:
    with Session(engine) as session, session.begin():
        lease = tasks.claim_task(session, task_id, worker_name)
    if lease is None:
        return WorkerResult(task_id, _status(engine, task_id))
    try:
        return _run_claimed(engine, lease, models, options)
    except tasks.LeaseLost:
        return WorkerResult(task_id, _status(engine, task_id), excluded=(("execution", "LEASE_LOST"),))
    except sa.exc.DBAPIError as error:
        _fail(engine, lease, _db_transient(error))
        # Raw driver text may contain candidate values; callers get only safe code.
        raise RuntimeError("EXTRACTION_DATABASE_FAILURE") from None
    except CallFailed as error:
        _fail(engine, lease, error.transient)
        raise RuntimeError(error.code) from None
    except Exception:
        _fail(engine, lease, False)
        raise


def _run_claimed(engine: Engine, lease: tasks.Lease, models: ModelStudio, options: WorkerOptions) -> WorkerResult:
    with _read(engine) as session:
        document, refs = inputs.require_effective_input(session, lease.task_id, options)
    body = extraction.extract_body(document, models, options.limits.body)
    if not body:
        return WorkerResult(lease.task_id, _finish_empty(engine, lease, valid=True), unavailable=refs.unavailable)
    proposals = _generation(engine, lease, body, refs, models, options)
    if proposals is None:
        return WorkerResult(lease.task_id, _status(engine, lease.task_id), unavailable=refs.unavailable)
    judged = extraction.judge_proposals(proposals, body, refs.ontology, models, options.limits)
    if judged.status == "FAILED":
        raise ValueError(judged.error_code or "EXTRACTION_VALIDATION_FAILED")
    exclusions = [(e.candidate_id, e.code) for e in judged.exclusions]
    with _read(engine) as session:
        prepared, resolution_exclusions = reconcile(session, judged.verified, document, refs, models, options)
    exclusions.extend(resolution_exclusions)
    if not prepared:
        with Session(engine) as session, session.begin():
            tasks.require_lease(session, lease)
            inputs.record_evidence_blocks(session, document, refs, proposals, exclusions)
            status = tasks.finish_product(session, lease, valid=not proposals.claims)
        return WorkerResult(lease.task_id, status, excluded=tuple(exclusions), unavailable=refs.unavailable)
    with Session(engine) as session, session.begin():
        tasks.require_lease(session, lease)
        current_document, current_refs = inputs.require_effective_input(session, lease.task_id, options)
        if current_document != document or current_refs != refs:
            raise ValueError("EXTRACTION_SNAPSHOT_CHANGED")
        batch_id = int(session.execute(sa.insert(db.promotion_batch).values(
            lint_policy_version_id=refs.lint_policy_id,
        ).returning(db.promotion_batch.c.promotion_batch_id)).scalar_one())
        inputs.record_evidence_blocks(session, document, refs, proposals, exclusions)
        applied = storage.write_prepared(session, batch_id, document, refs, prepared, options.statement_language)
        session.execute(sa.update(db.promotion_batch).where(db.promotion_batch.c.promotion_batch_id == batch_id).values(
            promotion_status="COMMITTED", committed_at=sa.func.clock_timestamp(),
        ))
        status = tasks.finish_product(session, lease, valid=True)
    return WorkerResult(lease.task_id, status, applied, tuple(exclusions), refs.unavailable)
