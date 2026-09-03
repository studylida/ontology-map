# ontology-map 구현 스택 기준

## 문서 상태

- 상태: 승인된 현재 구현 기준
- 확인일: 2026-09-03
- 관련 Issue: #38, #95–#100
- 실행 안내: [database-operations.md](database-operations.md)
- 코드 규칙: [code-conventions.md](code-conventions.md)

이 문서는 ontology-map의 실제 런타임, 직접 의존성, 프로세스와 코드 구조를 설명한다. 목표 구조를 미리 만들지 않고 현재 저장소와 lockfile에 존재하는 경계만 정식 상태로 기록한다.

## 기본 원칙

- 하나의 저장소에서 React web과 Python server를 관리한다.
- 브라우저와 PostgreSQL 사이의 유일한 제품 경계는 FastAPI HTTP API다.
- FastAPI route, 같은 프로세스의 application-service 함수와 SQLAlchemy query 함수를 구분한다.
- backend 내부 기능이나 DB 접근을 별도 HTTP service로 만들지 않는다.
- API와 worker는 같은 Python 코드와 image를 사용하고 실행 명령만 구분한다. 다만 worker는 아직 구현되지 않았다.
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

현재 `web/src/data.ts`는 exploration aggregate와 node search 응답을 화면 모델로 검증·변환한다. `App.tsx`는 기본 중심, 시간 범위, node·추천·후속 질문·검색 선택에 따른 새 exploration 요청과 loading·empty·error·retry를 소유한다. `GraphCanvas.tsx`는 런타임 layout과 2.5D 표시를, `DetailPanel.tsx`는 현재 탐색 정보 표시를 담당한다.

Relation·Evidence Trace와 peripheral endpoint는 server에 구현되어 있지만 web adapter는 각각 #118과 #115에 남아 있다. 인사이트 endpoint와 화면은 #68에 남아 있다.

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

LangChain과 provider integration은 설치되어 있지 않다. 실제 모델 호출과 worker 경계를 구현하는 Issue에서 provider, model ID와 호출 계약을 승인할 때만 필요한 직접 의존성을 추가한다.

## 현재 디렉터리와 의존 방향

```text
ontology-map/
├── compose.yaml
├── server/
│   ├── Dockerfile
│   ├── alembic.ini
│   ├── migrations/
│   │   └── versions/0001_create_frozen_schema.py
│   ├── src/ontology_map/
│   │   ├── main.py
│   │   ├── api.py
│   │   ├── exploration.py
│   │   ├── search.py
│   │   ├── relations.py
│   │   ├── pagination.py
│   │   ├── settings.py
│   │   └── db/
│   │       ├── schema.py
│   │       ├── session.py
│   │       ├── exploration.py
│   │       ├── search.py
│   │       ├── relations.py
│   │       └── fixture.py
│   └── tests/
└── web/
    ├── src/
    ├── package.json
    └── vite.config.ts
```

`main.py`는 application 생성과 시작 시 DB 연결 확인을 담당한다. `api.py`는 HTTP parsing, Pydantic DTO, 오류 변환과 application-service 호출만 담당한다. `exploration.py`, `search.py`, `relations.py`와 `pagination.py`는 같은 Python 프로세스에서 use case를 조합한다. `db/` 모듈은 SQLAlchemy session, 명시적인 SQL query, metadata와 개발 fixture를 소유한다.

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

개발 환경 설정부터 fixture, smoke check와 종료까지의 정확한 명령은 [database-operations.md](database-operations.md)를 따른다. API 컨테이너는 migration을 자동 실행하지 않으므로 migration과 fixture를 명시적으로 적용한 뒤 시작한다.

## 설정과 비밀 관리

server는 다음 환경 변수만 읽는다.

- `ONTOLOGY_MAP_DATABASE_URL`: SQLAlchemy용 PostgreSQL DSN
- `ONTOLOGY_MAP_ENVIRONMENT`: `development | test | production`

Compose는 `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`와 `POSTGRES_PORT`를 함께 사용한다. web은 브라우저에 공개 가능한 `VITE_DEFAULT_CENTER_NODE_ID`만 client bundle에서 읽고, `ONTOLOGY_MAP_API_PROXY_TARGET`은 Vite 개발 서버 설정에서만 사용한다.

실제 secret은 `.env`, source, log와 브라우저용 `VITE_*`에 넣지 않는다. 필수 server 설정이 없거나 DB 연결이 실패하면 애플리케이션 시작 단계에서 실패한다.

## 버전, 검사와 CI

`web/package.json`, `web/package-lock.json`, `server/pyproject.toml`과 `server/uv.lock`이 설치 계약을 소유한다. 버전 변경은 별도 Issue와 관련 검증을 거친다.

프로젝트 검사 명령은 다음과 같다.

| 대상 | 명령 |
| --- | --- |
| web | `npm run check` |
| server | `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy src`, `uv run --env-file ../.env pytest -q` |
| schema | `uv run --env-file ../.env alembic check` |

현재 GitHub Actions workflow는 없다. browser E2E, cloud deployment와 자동 release도 현재 기준에 포함되지 않는다.

## 승인된 계약과 남은 구현

- node 검색의 alias 정확 일치와 `simple` FTS는 구현되어 있다. Qwen `vector(1024)` cosine exact branch와 `k = 60` RRF는 #117에 남아 있다.
- 한국어 tokenizer, `pg_trgm`, BM25와 외부 검색 엔진은 #80의 benchmark 전에는 추가하지 않는다.
- HNSW와 IVFFlat은 #81의 측정 기준을 충족하지 못할 때만 검토하며 현재 성능 검증을 시작하지 않는다.
- 외부 source 수집, worker와 READY 전환 구현은 #111에 남아 있다.
- 후속 질문 생성 계약은 #113, 인사이트 생성·읽기·화면은 #68에 남아 있다.
- 인증, 관리자 기능, 배포 환경과 운영 인프라는 승인된 별도 Issue가 생길 때만 추가한다.
