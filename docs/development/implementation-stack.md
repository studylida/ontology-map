# ontology-map 구현 스택 기준

## 문서 상태

- 상태: 현재 구현과 승인된 변경·시험 구성을 구분한 기술 기준
- 확인일: 2026-09-09
- 구현 기준: `main`의 `997fd2a` (패널·지도 PR #161~#183 및 문서 #160 병합 후)
- 근거 대응: [#158](https://github.com/studylida/ontology-map/issues/158)
- 실행 안내: [DB 운영](../operations/database.md)
- 코드 규칙: [code-conventions.md](code-conventions.md)

이 문서는 실제 런타임·직접 의존성·프로세스와 코드 구조, 승인된 에이전트 역할과 모델 시험 구성을 설명한다. `현재 구현`은 위 commit과 lockfile, `승인·미구현`은 사용자 결정, `시험`은 제한된 실험을 뜻한다. 시험 모델·설정을 제품의 최종 고정 버전이나 품질 보증으로 해석하지 않는다. 상세 진행 이력과 미결정 사항은 연결된 Issue에서 관리한다.

## 기본 원칙

- 하나의 저장소에서 React web과 Python server를 관리한다.
- 브라우저와 PostgreSQL 사이의 유일한 제품 경계는 FastAPI HTTP API다.
- FastAPI route, 같은 프로세스의 application-service 함수와 SQLAlchemy query 함수를 구분한다.
- backend 내부 기능이나 DB 접근을 별도 HTTP service로 만들지 않는다.
- API와 향후 worker는 같은 Python 코드와 image를 사용하고 실행 명령만 구분하는 방향이다. 현재 worker 진입점은 없다.
- 테이블별 범용 CRUD repository, 구현 하나뿐인 interface와 미래용 abstraction을 만들지 않는다.
- Redis, Celery, LangGraph, API gateway와 microservice는 현재 스택에 없다.
- 직접 의존성은 정확한 버전으로 고정하고 전이 의존성은 lockfile로 관리한다.

## 런타임과 기반 서비스

| 구분 | 선택 | 기준 버전 |
| --- | --- | --- |
| JavaScript 런타임 | Node.js | 24.20.0 |
| JavaScript 패키지 관리자 | npm | 11.19.0 |
| Python 런타임 | Python | 3.14.7 |
| Python 프로젝트·패키지 관리자 | uv | 0.12.7 |
| 데이터베이스 | PostgreSQL | 18.6 |
| PostgreSQL vector 확장 | pgvector | 0.8.6 |

`compose.yaml`은 digest로 고정한 `pgvector/pgvector:0.8.6-pg18` DB와 FastAPI `api` service만 제공한다. web은 현재 호스트의 Vite 개발 서버로 실행한다.

## 프론트엔드

| 역할 | 직접 의존성 | 버전 |
| --- | --- | --- |
| UI | React, React DOM | 19.2.8 |
| 빌드·개발 서버 | Vite | 8.2.2 |
| 언어 | TypeScript | 7.0.2 |
| React plugin | `@vitejs/plugin-react` | 6.1.1 |
| graph | `3d-force-graph` | 1.80.0 |
| 3D rendering | Three.js | 0.185.0 |
| format·lint | Biome | 2.5.11 |
| test | Vitest, React Testing Library | 4.1.11, 16.3.3 |

web은 `fetch`로 상대 경로 `/api/v1`을 호출하고 Vite가 `ONTOLOGY_MAP_API_PROXY_TARGET`으로 proxy한다. 별도 HTTP client, query cache와 전역 상태 dependency는 없다.

`web/src/data.ts`는 exploration·검색·Relation·Evidence Trace·peripheral·인사이트 응답을 검증하고 화면 모델로 바꾼다. `App.tsx`는 URL의 중심·기간, 탐색 이력, 요청·전환과 오류를 관리한다. `useInitialLoading`, `usePeripheral`, `useCursorPage`는 초기 대기와 추가 page 조회를 나눈다. `GraphCanvas.tsx`와 `graphLayout`, `previewMotion`, `previewLabels`는 배치·카메라·이름 표시를, `DetailPanel`, `RelationPanel`, `InsightPanel`은 상세·근거·인사이트를 담당한다. `preview`라는 내부 이름은 별도 제품이나 미채택 화면을 뜻하지 않는다.

Relation·Evidence Trace, peripheral과 저장 인사이트 목록·상세는 server와 web adapter에 연결되어 있다. 생성 worker와 인사이트 품질 후속 작업은 #68에 남아 있다.

현재 활성 graph는 실제 3단계 이웃까지 포함하고, 주변부는 첫 page 자동 조회와 축소·경계 pan 후 cursor 조회를 사용한다. 추천은 실제 관계 경로를 표시한다. 기본 `/`와 `/design-preview`는 같은 화면이며 다크·라이트 모드, 초기 접근·정지·확대와 이름 페이드인을 제공한다. 시각 규칙과 사용자 흐름의 단일 기준은 [제품 설계](../product/design.md)다.

## 백엔드

| 역할 | 직접 의존성 | 버전 |
| --- | --- | --- |
| HTTP framework | FastAPI | 0.141.1 |
| ASGI server | Uvicorn | 0.52.4 |
| SQL·metadata | SQLAlchemy | 2.0.52 |
| migration | Alembic | 1.19.1 |
| PostgreSQL driver | psycopg | 3.3.4 |
| 입력·출력 검증 | Pydantic | 2.13.5 |
| 설정 | pydantic-settings | 2.15.0 |
| Python vector type | pgvector | 0.5.0 |
| test | pytest | 9.1.1 |
| format·lint | Ruff | 0.16.5 |
| typecheck | mypy | 2.3.1 |

LangChain과 provider integration은 설치되어 있지 않다. 제품 구현에는 LangChain의 필요한 최소 기능을 사용하기로 승인했으며 LangGraph·memory·자유로운 tool loop·별도 orchestrator는 도입하지 않는다. 이 프로젝트의 역할·실행 경계 결정은 [#125](https://github.com/studylida/ontology-map/issues/125)를 따른다. 제품 adapter 구현 시 최종 모델·호출 계약과 필요한 의존성을 확정한다.

## 에이전트 역할과 모델

### 승인된 역할과 제품 구현 상태

에이전트는 주어진 입력으로 생성·판정하고 일반 코드가 조회·실행 순서·검증·저장을 담당한다. 역할 하나가 별도 프로세스나 영속 `model_task` 하나라는 뜻은 아니다. 아래 역할은 제품 worker로 구현되지 않았다.

| 역할·작업 | 입력과 책임 | 모델 선택 상태 | 근거 |
| --- | --- | --- | --- |
| 본문 추출 | 입력 자료에서 분석할 본문만 추출하며 요약·번역·재작성하지 않음 | Flash 시험 방향. 최근 지식 추출 진단의 평가 대상에서는 제외 | [#111](https://github.com/studylida/ontology-map/issues/111), [#125](https://github.com/studylida/ontology-map/issues/125) |
| 지식 후보 작성 / `KNOWLEDGE_EXTRACTION` | 본문에서 의미·근거를 보존한 지식 후보 작성. Claim·Relation·attribute·event 대응은 상세 계약 검토 중 | Flash로 출발. 선정·작성 분리와 Selection의 Plus 사용은 아래 시험 구성 | [#127](https://github.com/studylida/ontology-map/issues/127) |
| Node 동일 대상 판정 / `ENTITY_RESOLUTION_PROPOSAL` | 일반 코드가 제공한 저장 Node 후보와 원문 안에서 판정. 이름·alias 일치만으로 확정하지 않음 | Plus 시험 방향. 제품 DTO·후보 조회 계약과 최종 모델 미확정 | [#128](https://github.com/studylida/ontology-map/issues/128) |
| Claim 의미 판정 | 정확한 재처리 중복은 코드로 처리하고 그 외 후보의 동일 의미를 판정. 코드 검증 후 기존 Claim 재사용·근거 추가 | Plus 시험 방향. 정확한 입력·출력과 task kind 매핑 미확정 | [#125](https://github.com/studylida/ontology-map/issues/125) |
| `FOLLOWUP_QUESTIONS` | 현재 node의 공개 node·Relation·Claim을 바탕으로 이해를 돕는 질문과 근거가 연결된 짧은 답변을 사전 생성하는 방향. 고정 총개수 없이 기간별로 저장하고 4개씩 읽음 | 생성 worker·모델·상세 출력 검증은 보류. #113의 이동형 두 질문은 #162로 대체 | [#162](https://github.com/studylida/ontology-map/issues/162), [#129](https://github.com/studylida/ontology-map/issues/129) |
| `NODE_CONTEXT`, `NODE_INSIGHT` | 공개 지식의 맥락·인사이트를 사전 생성. 현재 읽기 경로와 생성 구현을 구별 | 생성 adapter·모델 미확정. `NODE_CONTEXT`는 #129 범위 밖이며 후속 구현 소유 범위도 검토 필요 | [#124](https://github.com/studylida/ontology-map/issues/124), [#68](https://github.com/studylida/ontology-map/issues/68) |
| 충돌 후보 판정·`CONFLICT_SUMMARY` | 중복·관점·시점 차이와 모순의 구분 및 요약 필요성 검토 | 알고리즘·모델 배정 미승인 | [#130](https://github.com/studylida/ontology-map/issues/130) |
| `EVIDENCE_LINEAGE_PROPOSAL` | 독립 원문 계보 판정 계약 검토 | schema의 작업 종류는 있으나 실행 코드·모델 배정 없음 | [#64](https://github.com/studylida/ontology-map/issues/64), [#124](https://github.com/studylida/ontology-map/issues/124) |

### 제한된 모델 시험

[#139](https://github.com/studylida/ontology-map/issues/139)는 Alibaba Cloud Model Studio 싱가포르의 OpenAI 호환 endpoint에서 `qwen3.7-flash-2026-07-15`와 `qwen3.7-plus-2026-05-26` snapshot을 시험했다. 제품의 provider 방향과 시험 snapshot을 구별하며, 특정 제품 작업에 모델을 최종 고정한 것은 아니다. 원문·형식·의미 검증의 한계가 남아 자동 저장과 제품 worker는 완료되지 않았다.

| 시험용 역할 | 담당하는 일 | 배정·실행 상태 |
| --- | --- | --- |
| Selection | 선정·생략·보류, 사실 분리, 문장·modality·필수 요소·근거 선택 | Flash로 출발, R5 이후 Plus도 시험. R8까지 반복 진단 |
| Composer | Selection 문장을 Claim 문장으로 재작성 | Flash 배정. R8까지 새 구성 미실행, 추가 효용 비교 승인 |
| 보존 대응 검증 | 원문 필수 사실·조건이 Claim에 보존됐는지 판정 | Plus 배정. R8까지 새 구성 미실행, 정답표 없는 독립 평가 승인 |
| 원문·근거 충실도 검증 | Claim의 원문 지원, 근거 충분성·인용 범위·독립 사실 분리 판정 | Plus 배정. R8까지 새 구성 미실행, 독립 평가 승인 |

최근 네 역할 시험과 그 이전 Plus 오류 검증기를 구별한다. 이전 검증기는 알려진 의미 오류를 통과시킨 사례가 있으며 원문 ID 검사의 통과는 의미 오류 탐지 성공을 뜻하지 않는다. R8의 표본은 7개 지정 지점의 두 반복이고, 점수에는 의미 판단과 내부 표현 규칙이 섞여 있었다. `FACT` 값만으로 발언을 객관적 진실로 바꿨다고 단정하거나 이 표본으로 모델·thinking의 일반 성능을 결론 내리지 않는다. 점수와 후속 해석 정정은 [#139의 근거 보완](https://github.com/studylida/ontology-map/issues/139#issuecomment-5580299907)을 따른다.

승인된 후속 시험은 저장 출력의 평가 정리, Composer의 추가 효용, 정답표를 입력하지 않는 검증, 코드의 표 구조 지원 비교다. Selection 전체 통과가 다른 역할 시험을 막지 않도록 하고, 효과가 확인된 구성만 통합·새 장문 평가 대상으로 삼는다. 네 역할의 제품 유지 여부는 아직 정하지 않았다. 상세 라운드·점수·비용·실행 상태는 #139에서 관리한다.

초기 strict JSON Schema 시험과 최근 JSON Object·로컬 검증 시험은 서로 다른 호출 구성이다. `temperature`, thinking, 출력 상한도 라운드별 기록을 따르며 한 설정을 제품 기본값으로 옮기지 않는다. 특히 R8의 제한된 thinking은 대조 조건이며 후속 계획의 추가 thinking·streaming은 보류다. 시험 실행기는 제품 LangChain adapter가 아니다.

### 일반 코드와 저장 경계

- 원문 문장·표 행에 ID를 부여하고 선택한 ID의 Unicode 범위·인용문·hash를 복원한다. 모델의 인용 복사와 위치 계산을 대신하지만 의미의 정확성까지 보장하지 않는다. 실제 표의 행·열·머리글 지원은 후속 시험 대상이다.
- Node 후보는 화면이나 READY에 한정하지 않고 저장 Node에서 조회하는 방향이다. 현재 공개 검색 API를 내부 후보 조회로 그대로 대체하지 않는다. 조건부 새 Node 생성, alias 근거와 검증 실패 대상 우회 금지는 #125·#128을 따른다.
- 같은 endpoint·정확한 relation revision의 Relation을 재사용하고, 판정 불가 후보와 그 의존 후보를 제외한다. 남은 유효 지식은 의미를 훼손하지 않는 짧은 transaction으로 저장한다. 이 저장 service와 publication worker는 아직 없다.
- 기존 `model_task`, `agent_attempt`, `output_schema_definition`, Observation·Claim 근거 연결을 우선 재사용한다. runtime의 requirement·element·검증 역할을 새 DB 구조나 task kind로 확정하지 않는다. 영속 의미는 [논리 스키마](../data/logical-schema.md), 선정·보존 원칙은 [제품 설계](../product/design.md)가 소유한다.

## 현재 디렉터리와 의존 방향

```text
ontology-map/
├── compose.yaml
├── server/
│   ├── Dockerfile
│   ├── alembic.ini
│   ├── migrations/
│   │   └── versions/ (0001 frozen schema, 0002 panel reading)
│   ├── src/ontology_map/
│   │   ├── main.py
│   │   ├── api.py
│   │   ├── panel_api.py
│   │   ├── exploration.py
│   │   ├── search.py
│   │   ├── relations.py
│   │   ├── insights.py
│   │   ├── panel.py
│   │   ├── pagination.py
│   │   ├── settings.py
│   │   └── db/
│   │       ├── schema.py
│   │       ├── session.py
│   │       ├── exploration.py
│   │       ├── search.py
│   │       ├── relations.py
│   │       ├── insights.py
│   │       ├── panel.py
│   │       ├── fixture.py
│   │       ├── panel_fixture.py
│   │       └── review_fixture.py
│   └── tests/
└── web/
    ├── src/
    ├── package.json
    └── vite.config.ts
```

`main.py`는 application 생성과 시작 시 DB 연결 확인을 담당한다. `api.py`와 `panel_api.py`는 HTTP parsing, Pydantic DTO, 오류 변환과 application-service 호출만 담당한다. `exploration.py`, `search.py`, `relations.py`, `insights.py`, `panel.py`와 `pagination.py`는 같은 Python 프로세스에서 use case를 조합한다. `db/` 모듈은 SQLAlchemy session, 명시적인 SQL query, metadata와 개발 fixture를 소유한다.

의존 방향은 다음과 같다.

```text
browser
→ FastAPI route와 DTO
→ application-service 함수
→ SQLAlchemy query 함수
→ PostgreSQL
```

`db/`는 route나 web을 알지 않는다. route는 ORM row를 직접 반환하지 않는다. 읽기 요청은 `REPEATABLE READ`, read-only transaction에서 실행한다.

## 프로세스와 실행

| 프로세스 | 현재 상태 | 진입점 |
| --- | --- | --- |
| PostgreSQL | 구현 | `docker compose up -d db` |
| FastAPI | 구현 | `ontology_map.main:app` 또는 Compose `api` |
| web | 구현 | `web/`의 `npm run dev` |
| agent/worker | 미구현 | 없음 |

개발 환경 설정부터 fixture, smoke check와 종료까지의 정확한 명령은 [DB 운영](../operations/database.md)을 따른다. API 컨테이너는 migration을 자동 실행하지 않으므로 migration과 fixture를 명시적으로 적용한 뒤 시작한다.

## 설정과 비밀 관리

server는 다음 환경 변수만 읽는다.

- `ONTOLOGY_MAP_DATABASE_URL`: SQLAlchemy용 PostgreSQL DSN
- `ONTOLOGY_MAP_ENVIRONMENT`: `development | test | production`

Compose는 `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`와 `POSTGRES_PORT`를 함께 사용한다. web은 브라우저에 공개 가능한 `VITE_DEFAULT_CENTER_NODE_ID`만 client bundle에서 읽고, `ONTOLOGY_MAP_API_PROXY_TARGET`은 Vite 개발 서버 설정에서만 사용한다.

로컬 DB 예시 설정과 실제 provider secret을 구별한다. 실제 provider secret은 저장소 파일·log·브라우저용 `VITE_*`에 넣지 않는다. 시험의 WSL 외부 secret 주입은 제품 server 설정에 연결되어 있지 않다. 필수 server 설정이 없거나 DB 연결이 실패하면 애플리케이션 시작 단계에서 실패한다.

## 버전, 검사와 CI

`web/package.json`, `web/package-lock.json`, `server/pyproject.toml`과 `server/uv.lock`이 설치 계약을 소유한다. 버전 변경은 별도 Issue와 관련 검증을 거친다.

프로젝트 검사 명령은 다음과 같다.

| 대상 | 명령 |
| --- | --- |
| web | `npm run check` |
| server | `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy src`, `uv run --env-file ../.env pytest -q` |
| schema | `uv run --env-file ../.env alembic check` |
| 문서 | `uv run --project server --frozen python scripts/check_docs.py --check` |

모든 Pull Request에서 GitHub Actions가 DB 없이 문서 생성 결과, 저장소 내부 Markdown 링크와 ADR 규칙을 검사한다. 애플리케이션 검사 workflow, browser E2E, cloud deployment와 자동 release는 현재 기준에 포함되지 않는다.

## 현재 구현과 승인된 변경의 차이

| 영역 | 현재 구현 | 승인된 변경·후속 경계 |
| --- | --- | --- |
| 검색 | alias 정확 일치 뒤 `identity_text`·`knowledge_text`를 합친 `simple` FTS, 응답에 `match_reasons` 포함 | [#117](https://github.com/studylida/ontology-map/issues/117): alias → identity FTS → knowledge FTS, 이유 필드 제거. #121 뒤 구현 |
| embedding·pgvector | schema·migration·의존성과 합성 fixture에 남아 있으나 검색 실행 경로와 실제 모델 호출은 없음 | [#121](https://github.com/studylida/ontology-map/issues/121): 초기 baseline 교체와 개발 DB 재생성으로 제거. Qwen vector·RRF 도입안은 대체됐고 #81은 종료 |
| 한국어 검색 확장 | 외부 엔진·별도 tokenizer 없음 | [#80](https://github.com/studylida/ontology-map/issues/80): 실제 단어 FTS 누락이 재현될 때만 검토 |
| 공개 읽기 | exploration·검색·Relation·Evidence·peripheral·질문 답변·Claim·종합보고서 연동. #120의 selected search-document basis 재검증도 main에 반영됨 | [#180](https://github.com/studylida/ontology-map/issues/180): 무효화된 READY 파생 결과의 자동 재생성·publication 복구는 후속 작업 |
| 입력 자료 | HBF와 별도 100-node 합성 개발 fixture | [#111](https://github.com/studylida/ontology-map/issues/111)은 작은 자료의 Agent 입력 경계, #112는 GDELT 적합성, #131은 외부 자료 수집. 운영 수집 platform이나 publication 전체의 구현 Issue가 아님 |
| 생성·공개 | 저장된 context·질문·인사이트를 읽음 | 질문 생성은 #129, 인사이트 생성·품질은 #68. 수집→추출→판정→저장→READY의 실제 연동은 미완료 |

인증·관리자·배포 환경·운영 인프라는 승인된 별도 작업 없이 추가하지 않는다. schema의 존재, 합성 fixture와 개별 모델 시험을 실제 데이터 E2E 완료로 보지 않는다.
