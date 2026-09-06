---
id: ADR-0006
title: promotion과 publication 수명주기를 분리한다
status: accepted
decision_date: 2026-08-31
recorded_date: 2026-09-07
evidence: [#23](https://github.com/studylida/ontology-map/issues/23), [#46](https://github.com/studylida/ontology-map/issues/46), [PR #77](https://github.com/studylida/ontology-map/pull/77), [#95](https://github.com/studylida/ontology-map/issues/95), [PR #101](https://github.com/studylida/ontology-map/pull/101)
supersedes: none
superseded_by: none
affected_docs: [아키텍처](../../README.md), [논리 스키마](../../../data/logical-schema.md), [물리 스키마](../../../data/physical-schema.md)
---

# ADR-0006: promotion과 publication 수명주기를 분리한다

## 배경

검증된 Node, Relation과 Claim을 원자적으로 저장하는 일과 검색 문서, embedding, context, 질문 같은 공개용 파생 결과를 준비하는 일은 실패 원인과 재시도 범위가 다르다. 하나의 상태로 합치면 파생 작업 실패가 이미 저장된 기준 지식을 되돌리거나 이전 공개 결과를 잃게 만들 수 있다.

## 결정

`promotion_status`와 `publication_status`를 독립된 수명주기로 둔다. promotion은 기준 지식 저장의 원자 성공이나 실패를 나타내고, publication은 그 결과에 필요한 파생 산출물이 완결됐는지 나타낸다. 새 publication이 실패해도 저장된 기준 지식과 이전 `READY` 결과를 보존하며, 일반 조회는 최신 `COMMITTED + READY` 결과를 선택한다.

## 검토한 대안

- 적재와 공개를 하나의 성공 상태로 표현하는 방식은 부분 실패와 안전한 재시도를 구분할 수 없어 채택하지 않았다.
- publication 실패 때 기준 지식이나 이전 공개 결과를 삭제하는 방식은 검증된 데이터와 가용성을 함께 잃게 하므로 채택하지 않았다.

## 결과

기준 지식 저장과 파생 결과 준비를 독립적으로 재시도하고 이전 공개 결과를 계속 제공할 수 있다. 대신 여러 table의 완결성을 application service transaction에서 검사해야 한다. 현재 schema와 읽기 경로는 이 계약을 표현하지만 promotion·publication worker는 아직 구현되지 않았다.

## 근거

[#23](https://github.com/studylida/ontology-map/issues/23)이 수명주기 분리를 결정했고, [#46](https://github.com/studylida/ontology-map/issues/46)과 [PR #77](https://github.com/studylida/ontology-map/pull/77)이 물리 계약을 확정했다. [#95](https://github.com/studylida/ontology-map/issues/95)와 [PR #101](https://github.com/studylida/ontology-map/pull/101)이 metadata와 migration에 구현했다.
