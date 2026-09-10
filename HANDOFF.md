# ontology-map #110 데이터 정책 인계

> 확인일: 2026-09-10. 작업 기준은 `main`의 `6edea5498d54540f4c04029bb6f88adf60043f2f`이며, 이후 상태는 GitHub와 실제 commit을 다시 확인한다.

## 확정한 정책

- [#110](https://github.com/studylida/ontology-map/issues/110)의 [출처·lint 적재 정책](docs/data/source-intake-policy.md)은 lint를 계약 유효 후보와 저장 그래프의 Evidence Trace·온톨로지·무결성 검사로 확정했다. 데이터 원천·corpus·모델 품질·출처 점수와는 구분한다.
- 공개 공식 문서와 발행 주체·편집 책임을 식별할 수 있는 자료만 저장 전 자격을 통과한다. 접근 제한 우회, 유출·익명 개인 자료와 고위험 개인정보가 있는 문서는 받지 않는다.
- 출처 자격 뒤 [#64 계보 정책](docs/data/evidence-lineage-policy.md)을 적용한다. 같은 원문 계보와 같은 사건은 다르며, 계보가 모호하면 `source_document`를 만들지 않는다.
- 부분 `BLOCKING`은 후보와 의존 후보만 제외하고 유효 후보를 원자 승격한다. 전체 차단은 `VALIDATION_BLOCKED`, 관련 후보 없음은 `SUCCESS`와 0개 결과다. 성공한 full graph lint만 기존 finding을 해결한다.
- publication 실패는 기준 지식과 이전 유효 `READY`를 유지한다. 실패 원인의 자동 복구는 구현되지 않았으며 [#180](https://github.com/studylida/ontology-map/issues/180)에 남아 있다.

## 구현·검증 경계

- #110은 정책 문서만 바꾸며 수집기·worker·lint 실행기·모델 호출, schema·migration·API·fixture와 실제 DB 적재를 구현하지 않는다.
- #131 공개 manifest의 직접·배경 관련성, 중복 URL·본문 사례로 입력 경계를 확인한다. 이는 Agent·DB·publication 실행이나 추출·모델 품질의 증거가 아니다.
- #131은 시연용 일회성 corpus이며 향후 제품 입력은 다른 주체가 모집·제공한 자료를 받는다. 제품에 운영 수집 플랫폼을 추가하지 않는다.
- 삭제·takedown·controlled purge와 자동 복구는 이번 범위가 아니다.

## 다음 작업

- [#124](https://github.com/studylida/ontology-map/issues/124)는 Agent 역할과 frozen schema 정합성을 확정하고, [#126](https://github.com/studylida/ontology-map/issues/126)은 초기 Relation·attribute·Topic 목록을 정한다.
- [#111](https://github.com/studylida/ontology-map/issues/111)은 #131의 검증 자료 중 작은 집합을 본문 추출 Agent 입력 경계로 넘긴다. 시작 전 #124와 현재 다른 세션의 소유 상태를 다시 확인한다.
- #127의 지식 후보 작성, #128의 Node 동일 대상 판정과 실제 저장·publication 구현은 각각 승인된 범위에서 진행한다. #68·#129의 생성 작업과 #139의 추가 모델 시험을 이 정책으로 재개하지 않는다.
