# ontology-map 현재 상태 인계

> 인계본 작성: `2026-09-03T14:20+09:00`, 기준 `main`: `8073f64`, 확인 완료: 2026-09-03T14:27+09:00 / Ontology Map Schema/API Drift Audit
>
> 이 문서는 새 세션이 인계를 확인할 때만 사용하는 임시 문서다. 확인이 끝나면 다음 인계 내용으로 교체하거나 `archive/`로 옮긴다.

## 기준 상태

- 기준 `main`: `8073f64ef1d63ee9f6387a58b0e9b250be7141e1` (`feat: 주변부 cursor 조회 API 추가`)
- `origin/main`: 위 commit과 동일
- 열린 PR: 없음
- 현재 문서 작업: Issue #105는 @studylida가 점유한 `status: in progress` 상태다. Branch `docs/105-consolidate-documentation`에는 문서 통합 commit `46897e9`, 확인 상태 commit `f02b49d`와 이 인계본을 담은 현재 HEAD가 있으며, 전체 목록은 `git log --oneline origin/main..HEAD`로 확인한다. Push와 PR 생성은 승인받지 않아 진행하지 않았다.
- 기타 로컬 worktree와 branch에는 이미 squash 병합된 Issue의 과거 작업점이 남아 있다. 새 작업에 재사용하기 전에 Issue 소유권, 변경 상태와 `main` 포함 여부를 다시 확인한다.

## 완료된 구현

| Issue | 병합 결과 | 실제 범위 |
| --- | --- | --- |
| #90 | `daa0bf2` | 탐색 허브 panel 정보 구조 개편 |
| #91, #48 | `1f3793f`, `713e0e7` | 인사이트 논리·물리 schema와 전체 schema 재검증 |
| #95 | `d5722d2` | FastAPI·SQLAlchemy·Alembic 실행 기반, frozen schema migration, Compose와 개발용 HBF fixture |
| #96 | `24a2c77` | 중심 node와 시간 범위 기반 exploration aggregate API |
| #97 | `5019ab1` | alias 정확 일치와 PostgreSQL `simple` FTS node 검색 API |
| #100 | `5c7eb07` | web의 exploration·search adapter, loading·empty·error·retry와 중심 전환 요청 |
| #98 | `f9685df` | node Relation 목록과 Relation Evidence Trace API |
| #99 | `8073f64` | 주변부 공개 node의 opaque cursor API |

## 현재 HTTP와 web 연동 상태

| Endpoint | backend | web |
| --- | --- | --- |
| `GET /api/v1/exploration/{center_node_id}` | 구현 | 연동 완료 |
| `GET /api/v1/nodes/search` | alias·FTS 구현 | 연동 완료 |
| `GET /api/v1/nodes/{node_id}/relations` | 구현 | 미연동, #118 |
| `GET /api/v1/relations/{relation_id}/evidence` | 구현 | 미연동, #118 |
| `GET /api/v1/exploration/{center_node_id}/peripheral` | 구현 | 미연동, #115 |
| node 인사이트 목록·상세 | 미구현, #68 | 미구현, #68 |

search의 Qwen cosine exact vector branch와 `k = 60` RRF는 #117에 남아 있다. 현재 web은 API가 구현된 exploration과 alias·FTS 검색만 사용한다. 브라우저는 PostgreSQL에 직접 접근하지 않는다.

## 문서 정리 결과

- 루트의 정식 문서는 `README.md`, `database-operations.md`, `code-conventions.md`, `CONTRIBUTING.md`, `DESIGN.md`, `implementation-stack.md`, `logical-data-schema.md`와 `physical-data-schema.md`로 제한했다.
- 완료된 Issue별 schema 문서, 과거 요구사항 추적표와 대화 기록은 현재 결론을 정식 문서에 반영한 뒤 `archive/`로 옮겼다.
- `HANDOFF.md`는 정식 계약이 아니라 현재 작업 상태만 전달한다.

## 열린 후속 Issue

- #64: 준비 문서의 독립 근거 묶음 판정 전략
- #68: 사전 생성 인사이트의 품질, 읽기 API와 화면 구현
- #80: 한국어 검색 품질 benchmark와 확장 방식 결정
- #81: 필요할 때만 exact search 성능과 ANN 전환 검증
- #106: node와 label 가독성 개선. 사용자가 반복 검토하고 조언한다.
- #107: 빈 map drag pan 회귀 복구
- #110: lint 적용 대상과 적재 정책 확정
- #111: 외부 source 수집 pipeline과 READY 전환 경계 설계
- #112: GDELT 기반 SK하이닉스 E2E 데이터셋 적합성 조사
- #113: 후속 질문 생성·갱신 제품 계약 확정
- #114: 중심 node 전환 시 graph 재배치 회귀 복구
- #115: 주변부 cursor paging web 연동
- #116: frontend·backend와 frozen schema의 필드별 drift 감사
- #117: Qwen exact vector branch와 RRF 기준선 구현
- #118: Relation과 Evidence Trace web 연동

## 권장 다음 순서

1. GitHub의 전체 Issue를 처음 번호부터 현재까지 훑어 제목, 상태, 의존 관계, 결정 변경과 실제 병합 결과를 파악한다. 번호가 가깝다는 이유만으로 선행 관계를 추측하지 않는다.
2. 전체 흐름을 논리 schema 정리, 물리 schema 확정, 디자인·frontend POC, backend·web 연동, 열린 제품·데이터 작업 단계로 요약하고 현재 코드와 대조한다.
3. #116의 read-only 감사를 수행해 현재 응답 필드와 frozen schema를 정확히 대응하고 실제 계약 위반만 별도 수정 Issue로 연결한다.
4. 화면 회귀는 #107, #114와 #106의 관계를 확인하고 사용자의 반복 검토를 받는다.
5. 이미 구현된 backend를 활용하는 #118과 #115를 진행한다.
6. #117의 검색 기준선을 구현한 뒤 #80을 수행하고, 실제 성능 문제가 확인될 때만 #81을 시작한다.
7. #64와 #110의 정책을 확정한 뒤 #111을 설계하고 #112의 작은 표본 조사를 진행한다.
8. #113의 질문 계약과 #68의 인사이트 계약을 확정한 뒤 같은 Python 코드와 image를 사용하는 worker 흐름을 구현한다.

## 다음 세션 인계 메모

- 사용자가 `Ontology Map Documentation Consolidation` 세션의 작업을 다음 세션으로 명시적으로 인계했다. 다음 세션은 위 상태 표시를 먼저 갱신하고 #105의 최근 댓글에 새 세션과 작업 범위를 기록한다. 이 두 인계 처리 외의 tracked file이나 원격 상태는 그다음에 변경한다.
- #105의 로컬 commit은 새로 재현할 작업이 아니다. 기존 worktree에서 diff와 검증 결과를 확인하고, push·PR·병합은 사용자가 각 작업을 명시적으로 승인할 때만 진행한다.
- 전체 Issue 조사는 먼저 모든 Issue의 번호, 제목, 상태, label과 생성·종료 시각을 한 번에 확인한다. 그다음 계약을 바꿨거나 구현·병합 결과가 불명확한 Issue만 본문, 결정 댓글과 연결된 commit을 읽어 context를 제한한다.
- 진행 흐름을 요약할 때 완료된 작업, 뒤의 결정으로 대체된 작업, 아직 열려 있는 작업을 구분한다. 과거 Issue의 설명이 현재 정식 문서와 다르면 frozen schema, 병합된 코드와 최신 GitHub 결정 순으로 확인한다.
- 현재 디렉터리 구조는 POC 범위에 적절하다고 판단했다. 파일 길이만으로 구조 개편 Issue를 만들지 않으며 #68, #106, #107 또는 #114에서 실제 책임 충돌이 확인될 때 가장 가까운 기능만 분리한다.
- #99의 확정 범위는 현재 page의 주변부 node와 활성 graph 사이의 실제 공개 Relation만 반환하는 것이다. Relation 60개 제한은 활성 graph에만 적용하고 주변부 응답에는 별도 Relation 상한을 두지 않는다.
- 사용자는 현재 단계에서 성능 검증이 필요하지 않다고 결정했다. #81은 #117의 exact vector·RRF 구현과 실제 측정 데이터가 준비된 뒤에도 성능 문제가 확인될 때만 시작한다.
- 다음 권장 작업인 #116은 read-only 계약 감사다. 감사 중 코드·schema·정식 문서를 수정하지 않고 각 항목을 `일치 | HTTP 표현 | 미구현 | 계약 위반 | 결정 필요`로 판정한 뒤, 수정이 필요하면 기존 Issue에 연결하거나 별도 Issue 제안으로 끝낸다.

## 차단 사항과 결정 항목

- agent/worker 실행 명령, 외부 source, 수집 manifest와 실제 READY publication 전환 구현은 아직 없다.
- LINT가 현재 lint 검증 계층 외의 별도 데이터 원천이나 corpus를 뜻하는지는 #110에서 명시적으로 결정해야 한다.
- GDELT의 endpoint, HTTP 지원, 한국어 품질과 원문 보존 가능 범위는 #112에서 공식 근거와 작은 표본으로 확인해야 한다.
- Relation·Evidence Trace, peripheral과 insight를 상세 panel에 배치하는 세부 UX는 관련 frontend Issue에서 사용자가 직접 검토한다.
- exploration aggregate에는 peripheral `next_cursor`가 없다. #115는 첫 page를 cursor 없이 요청하고 이후 page만 응답 cursor로 요청하는 현재 계약을 기본으로 삼으며, aggregate가 가능 여부를 미리 알려야 한다면 별도 backend 계약 변경이 필요하다.
- 이전 READY가 전혀 없는 publication 실패의 `503` 정책은 현재 exploration 계열에서 적용되며, worker와 인사이트에서도 유지할지는 #68과 #111에서 최종 확인한다.
