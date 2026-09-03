# ontology-map 로컬 실행과 DB 운영

이 문서는 PostgreSQL, migration, 개발용 HBF fixture, FastAPI와 web을 한 번에 실행하는 기준 절차다. 브라우저는 Vite proxy를 통해 FastAPI만 호출하며 PostgreSQL에 직접 접근하지 않는다.

## 요구 버전

| 항목 | 버전 |
| --- | --- |
| Python | 3.14.7 |
| uv | 0.12.7 |
| Node.js | 24.20.0 |
| npm | 11.19.0 |
| PostgreSQL image | 18.6 |
| pgvector image | 0.8.6 |

Docker Desktop을 쓰는 Windows 환경에서는 현재 WSL distribution의 Docker integration을 먼저 켜고 WSL에서 `docker version`과 `docker compose version`이 모두 성공하는지 확인한다.

## 1. 환경 변수 준비

저장소 루트에서 개발 환경 파일을 만든다.

```bash
cp .env.example .env
```

`.env`의 빈 값은 다음 형식으로 채운다. 이 값은 로컬 개발 예시이므로 공유 환경의 credential로 재사용하지 않는다.

```dotenv
POSTGRES_DB=ontology_map
POSTGRES_USER=ontology_map
POSTGRES_PASSWORD=ontology_map-local
POSTGRES_PORT=5432
ONTOLOGY_MAP_ENVIRONMENT=development
ONTOLOGY_MAP_DATABASE_URL=postgresql+psycopg://ontology_map:ontology_map-local@127.0.0.1:5432/ontology_map
```

`ONTOLOGY_MAP_DATABASE_URL`의 사용자, 비밀번호, 포트와 데이터베이스 이름은 같은 파일의 `POSTGRES_*` 값과 일치해야 한다. 실제 secret은 `.env.example`이나 Git에 넣지 않는다.

## 2. PostgreSQL과 migration

저장소 루트에서 PostgreSQL을 시작한다.

```bash
docker compose up -d db
docker compose ps
```

`server/`에서 고정된 의존성을 설치하고 Alembic migration을 적용한다.

```bash
cd server
uv sync --frozen
uv run --env-file ../.env alembic upgrade head
uv run --env-file ../.env alembic current
```

현재 기준 revision은 `0001_create_frozen_schema.py` 한 개다. PostgreSQL 객체는 `public` schema에 만들며 migration과 SQLAlchemy metadata는 같은 frozen schema를 표현한다.

## 3. 개발용 HBF fixture

`server/`에서 fixture 명령을 실행한다.

```bash
PYTHONPATH=src uv run --env-file ../.env python -m ontology_map.db.fixture
```

fixture는 `ONTOLOGY_MAP_ENVIRONMENT=development`에서만 동작하고 같은 DB에 다시 실행해도 중복 행을 만들지 않는다. 출력에는 `sk_hynix`, `hbf` 등 node 이름별 bigint ID가 표시된다. 이 값 중 하나를 web의 기본 중심으로 사용한다.

이 fixture는 개발용 고정 데이터다. 외부 source에서 수집한 운영 데이터나 모델의 실제 출력으로 해석하지 않는다.

## 4. FastAPI 실행

호스트에서 실행하려면 `server/`에서 다음 명령을 사용한다.

```bash
PYTHONPATH=src uv run --env-file ../.env uvicorn ontology_map.main:app --reload
```

Docker에서 실행하려면 migration과 fixture를 먼저 적용한 뒤 저장소 루트에서 다음 명령을 사용한다.

```bash
docker compose up --build api
```

API는 기본적으로 `http://127.0.0.1:8000`에서 열리고 OpenAPI UI는 `http://127.0.0.1:8000/docs`에서 확인할 수 있다. 별도 health endpoint는 없다. 애플리케이션은 시작할 때 `SELECT 1`로 DB 연결을 확인하며 실패하면 시작하지 않는다.

## 5. web 실행

새 terminal에서 `web/`로 이동해 환경 파일을 만든다.

```bash
cd web
cp .env.example .env.local
npm ci
```

`.env.local`의 `VITE_DEFAULT_CENTER_NODE_ID`에는 HBF fixture가 출력한 node ID 하나를 문자열 그대로 넣는다. API를 기본 주소가 아닌 곳에서 실행할 때만 proxy target을 바꾼다.

```dotenv
VITE_DEFAULT_CENTER_NODE_ID=1
ONTOLOGY_MAP_API_PROXY_TARGET=http://127.0.0.1:8000
```

다음 명령으로 Vite 개발 서버를 시작한다.

```bash
npm run dev
```

브라우저에서 Vite가 출력한 주소를 열면 web은 `/api/v1` 요청을 FastAPI로 전달한다. `VITE_DEFAULT_CENTER_NODE_ID`가 없거나 공개할 수 없는 ID이면 초기 화면에 설정 또는 API 오류가 표시된다.

## 6. 최소 smoke check

fixture가 출력한 실제 ID를 전용 shell 변수에 넣는다. 다음 `1`은 형식 예시이므로 현재 DB의 출력값으로 바꾼다.

```bash
export ONTOLOGY_MAP_CENTER_ID='1'
curl --fail "http://127.0.0.1:8000/api/v1/exploration/${ONTOLOGY_MAP_CENTER_ID}?time_window=RECENT_90_DAYS"
curl --fail --get 'http://127.0.0.1:8000/api/v1/nodes/search' --data-urlencode 'q=SK하이닉스' --data 'limit=5'
```

브라우저에서는 기본 중심 graph가 열리고, node 선택과 `RECENT_90_DAYS`·`RECENT_1_YEAR` 변경 및 검색 결과 선택이 새 exploration 요청으로 이어지는지 확인한다. Relation·Evidence Trace와 peripheral endpoint는 backend에 있지만 현재 web adapter는 없다. 인사이트 endpoint와 worker는 아직 구현되지 않았다.

## 7. 검사

PostgreSQL이 실행 중이고 migration이 적용된 상태에서 `server/` 검사를 실행한다.

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run --env-file ../.env pytest -q
uv run --env-file ../.env alembic check
```

`web/` 검사는 다음 명령 하나로 format, lint, typecheck, component test와 production build를 순서대로 실행한다.

```bash
npm run check
```

## 8. agent와 worker

현재 `server/`에는 agent/worker 진입점과 실행 명령이 없다. 실행 가능한 것처럼 임시 명령을 만들지 않는다. 외부 수집·publication worker는 #111, 후속 질문 계약은 #113, 인사이트 생성과 읽기는 #68에서 다룬다.

API와 worker는 구현된 뒤에도 같은 Python 코드와 image를 사용하고 실행 명령만 구분한다. Redis, Celery, LangGraph와 별도 microservice는 실제 필요가 승인되기 전에는 추가하지 않는다.

## 9. 종료와 초기화

컨테이너를 멈추되 DB volume을 보존하려면 저장소 루트에서 실행한다.

```bash
docker compose down
```

개발 DB를 완전히 다시 만들 때만 다음 명령을 사용한다. 이 명령은 `ontology-map-postgres` volume과 안의 로컬 데이터를 삭제하므로 되돌릴 수 없다.

```bash
docker compose down --volumes
```

초기화한 뒤에는 PostgreSQL 시작, migration과 fixture 단계를 다시 수행한다.
