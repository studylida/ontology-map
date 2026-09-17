# Initial publication durable execution (#215)

## 상태

- 확인일: 2026-09-17
- 통합 기준 main: `06cc901c64c4f72fa0e2a0577f23235600280cc0`
- migration head: `0006_add_provider_call_slot.py`
- 대상: [Issue #215](https://github.com/studylida/ontology-map/issues/215), Draft PR #220

이 문서는 #215 initial publication의 현재 구현 책임과 durable execution 연결만 설명한다. #180의 READY 이후 recovery를 포함하지 않으며, 실제 shared/product DB enable 상태를 뜻하지 않는다.

## 현재 main dependency

현재 main에는 다음 선행 경계가 존재한다.

- #216 `promotion_canonical_change`와 migration `0005_add_promotion_canonical_change.py`
- #127 공통 durable `model_task` lease/retry, `provider_call_slot`, `agent_attempt`, migration `0006_add_provider_call_slot.py`
- #129 `FOLLOWUP_QUESTIONS` durable task identity, provider adapter, runner
- #68 `NODE_INSIGHT` 90일+1년 atomic durable task identity, provider adapter, runner

#215는 위 lifecycle과 #129/#68 제품 의미를 복제하지 않는다.

## Initial publication 흐름

```text
promotion COMMITTED
→ start_initial_publication()
→ publication_affected_node frozen membership
→ deterministic node_search_document
→ NODE_CONTEXT durable task/runner
→ FOLLOWUP RECENT_90_DAYS durable runner
→ FOLLOWUP RECENT_1_YEAR durable runner
→ NODE_INSIGHT 90d+1y atomic durable runner
→ publication_readiness()
→ mark_publication_ready()
→ READY
```

`initial_publication_coordinator.run_initial_publication()`은 이 dependency order만 조합한다. 범용 queue, scheduler, workflow table, 별도 attempt 원장을 추가하지 않는다.

## Durable ownership

`NODE_CONTEXT`는 #215 제품이므로 #215가 task-specific provider adapter와 runner를 소유한다. 다만 claim/lease, retry/backoff, provider call slot, `agent_attempt`, provider outcome 기록은 모두 #127 공통 `db.model_tasks`와 `durable_provider`를 사용한다. 기존 `prepare_node_context()`, `ensure_node_context_task()`, `apply_node_context()`가 generation identity, stale 검증, immutable artifact와 product terminal 의미의 source of truth다.

FOLLOWUP은 `db.followup_tasks.enqueue_followup()`과 `followup_runner.run_followup()`을 사용한다. 90일과 1년은 #129가 소유하는 서로 다른 durable task이며 #215가 input hash/cache key를 계산하지 않는다.

NODE_INSIGHT는 `db.insight_tasks.enqueue_insight()`과 `insight_runner.run_insight()`을 사용한다. 한 durable task가 90일+1년 전체 bundle을 소유하며 #215는 기간별 Insight task를 만들지 않는다.

## Restart와 READY

같은 batch 재실행은 frozen membership과 기존 deterministic search document를 재사용하고, 각 task-owned durable identity로 기존 task를 찾는다. `SUCCESS`, `RUNNING`, `RETRY_WAIT`, `VALIDATION_BLOCKED`, `FINAL_FAILED`를 #215가 초기화하거나 다른 의미로 바꾸지 않는다. terminal `SUCCESS` task에는 provider send를 반복하지 않는다.

READY는 runner 성공만으로 전환하지 않는다. 기존 `publication_readiness()`가 같은 publication generation의 search document, NODE_CONTEXT, FOLLOWUP 90일·1년, NODE_INSIGHT atomic bundle과 stale 상태를 모두 검증한 뒤에만 기존 `mark_publication_ready()`를 호출한다.

PREPARING 이후 affected membership의 authoritative source는 `publication_affected_node`다. #216 provenance는 최초 `NOT_STARTED → PREPARING` 진입 때만 membership 산정에 사용하고 READY/failure/retry에서 재projection하지 않는다.

## 검증과 운영 경계

격리 PostgreSQL 회귀는 실제 durable claim → slot reservation commit → provider operation → `agent_attempt` terminal → exact lease fence → product finalizer → READY 순서를 검증한다. CI provider operation은 deterministic injected operation 또는 MockTransport를 사용할 수 있으며 유료 Model Studio 호출과 구분한다.

실제 shared/product DB coordinator enable 전에는 current migration head 적용과 `assert_initial_publication_cutover_safe()` PASS가 별도로 필요하다. legacy `COMMITTED + NOT_STARTED`가 발견되면 자동 추정·skip하지 않고 remediation 대상으로 분리한다.

READY 이후 effective public basis invalidation과 recovery는 #180 소유다. #215는 #216 provenance를 recovery event log나 reconciliation identity로 사용하지 않는다.
