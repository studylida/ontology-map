# ontology-map 백엔드

## 로컬 실행

저장소 루트에서 개발 환경 파일을 만들고 빈 값을 채운 뒤 PostgreSQL을 시작한다. `ONTOLOGY_MAP_DATABASE_URL`의 사용자, 비밀번호, 포트와 데이터베이스 이름은 같은 파일의 `POSTGRES_*` 값과 일치해야 한다.

```bash
cp .env.example .env
docker compose up -d db
```

`server/`에서 고정된 의존성을 설치하고 migration과 HBF fixture를 적용한다.

```bash
uv sync --frozen
uv run --env-file ../.env alembic upgrade head
PYTHONPATH=src uv run --env-file ../.env python -m ontology_map.db.fixture
```

API는 호스트 또는 Compose에서 실행할 수 있다.

```bash
PYTHONPATH=src uv run --env-file ../.env uvicorn ontology_map.main:app --reload
```

```bash
docker compose up --build api
```

HBF fixture는 `ONTOLOGY_MAP_ENVIRONMENT=development`에서만 실행된다. 같은 데이터베이스에 다시 적용해도 기존 fixture 행을 중복 생성하지 않는다.

## 검사

PostgreSQL이 실행 중이고 migration이 적용된 상태에서 다음 명령을 사용한다.

```bash
uv sync --frozen
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run --env-file ../.env pytest -q
uv run --env-file ../.env alembic check
```
