# ontology-map 구현 스택 기준

## 문서 상태

- 상태: 승인된 구현 기준
- 확인일: 2026-09-01
- 관련 Issue: #38
- 후속 Issue: #8 코드 컨벤션 정의

이 문서는 축약 스키마를 받기 전에 합의한 ontology-map의 구현 스택, 목표 폴더 구조, 환경 변수, 의존성, 실행 프로세스와 CI 기준을 기록한다. 현재 저장소에 코드, 스키마, 의존성, 설정 파일이나 실행 환경을 추가하는 지시가 아니며, 실제 생성은 축약 스키마 검토와 별도 승인 이후에 진행한다.

## 기본 원칙

- 하나의 저장소에서 TypeScript 프론트엔드와 Python 백엔드·에이전트를 관리한다.
- 로컬 실행은 Docker Compose를 기준으로 하되, API와 worker는 같은 Python 코드와 이미지를 사용하고 실행 명령만 구분한다.
- POC에는 인증, 클라우드 배포, 브라우저 E2E, 자동 모델 fallback과 통합 모델 gateway를 도입하지 않는다.
- 직접 의존성은 정확한 버전으로 고정하고, 사용하지 않는 provider integration은 설치하지 않는다.
- 데이터베이스 구조와 migration은 축약 스키마 승인 전까지 만들지 않는다.

## 런타임과 기반 서비스

| 구분 | 선택 | 기준 버전 |
| --- | --- | --- |
| JavaScript 런타임 | Node.js LTS | 24.20.0 |
| JavaScript 패키지 관리자 | npm | 11.19.0 |
| Python 런타임 | Python | 3.14.7 |
| Python 프로젝트·패키지 관리자 | uv | 0.12.7 |
| 데이터베이스 | PostgreSQL | 18.6 |
| 벡터 확장 | pgvector 서버 확장 | 0.8.6 |

## 프론트엔드

| 역할 | 패키지 | 기준 버전 |
| --- | --- | --- |
| UI | React | 19.2.8 |
| DOM 렌더러 | React DOM | 19.2.8 |
| 빌드 도구 | Vite | 8.2.2 |
| 언어 | TypeScript | 7.0.2 |
| React 플러그인 | @vitejs/plugin-react | 6.1.1 |
| 그래프 시각화 우선 검증 후보 | 3d-force-graph | 1.80.0 |
| 그래프 시각화 비교 후보 | Reagraph | 4.32.0 |
| 포맷·lint | Biome | 2.5.11 |
| 단위·컴포넌트 테스트 | Vitest | 4.1.11 |
| React 테스트 유틸리티 | React Testing Library | 16.3.3 |

3d-force-graph를 POC의 우선 검증 후보로 삼고 Reagraph는 비교 대상으로만 유지한다. 두 라이브러리를 동시에 제품 의존성으로 추가하지 않으며, 지식맵의 클릭·중심 이동·직접 이웃과 중요 2단계 이웃 표시 요구를 가장 단순하게 충족하는 후보 하나만 채택한다.

Next.js와 저장소 공통 패키지는 현재 필요하지 않으므로 만들지 않는다. 웹 앱은 Vite 기반의 단일 React 애플리케이션으로 시작한다.

## 백엔드와 에이전트

| 역할 | 패키지 | 기준 버전 |
| --- | --- | --- |
| API 프레임워크 | FastAPI | 0.141.1 |
| ASGI 서버 | Uvicorn | 0.52.4 |
| ORM·SQL 도구 | SQLAlchemy | 2.0.52 |
| migration | Alembic | 1.19.1 |
| PostgreSQL 드라이버 | psycopg | 3.3.4 |
| 데이터 검증 | Pydantic | 2.13.5 |
| 설정 로딩 | pydantic-settings | 2.15.0 |
| 모델 공통 인터페이스 | langchain | 1.3.18 |
| 최초 모델 provider integration | langchain-openai | 1.6.0 |
| Python 벡터 타입 연동 | pgvector | 0.5.0 |
| 테스트 | pytest | 9.1.1 |
| 포맷·lint | Ruff | 0.16.5 |
| 정적 타입 검사 | mypy | 2.3.1 |

Celery, Redis와 LangGraph는 POC의 고정 작업 흐름과 재시도 요구에 필요하지 않으므로 도입하지 않는다. 일반 Python 작업 실행 코드와 데이터베이스 상태로 작업을 관리하고, 실제 요구가 확인될 때만 별도 큐나 workflow engine을 검토한다.

## 목표 폴더 구조

```text
ontology-map/
├── web/
└── server/
    ├── migrations/
    └── src/
        └── ontology_map/
            ├── api/
            ├── agent/
            └── db/
```

- `web/`은 React 애플리케이션과 프론트엔드 전용 설정을 둔다.
- `server/src/ontology_map/api/`는 HTTP 경계, 요청·응답 검증과 API 조합을 담당한다.
- `server/src/ontology_map/agent/`는 모델 작업별 prompt, structured output과 실행 흐름을 담당한다.
- `server/src/ontology_map/db/`는 데이터베이스 연결과 영속성 코드를 담당한다.
- `server/migrations/`는 축약 스키마 승인 이후 Alembic migration만 둔다.

초기에는 이보다 더 세분화된 layer, 공유 package나 추상화 폴더를 만들지 않는다. 코드가 생긴 뒤 실제 책임이 겹칠 때 Issue #8의 코드 컨벤션에서 경계를 구체화한다.

## 실행 프로세스

향후 로컬 Compose는 `web`, `api`, `worker`, `db` 네 서비스를 제공한다. `api`와 `worker`는 같은 Python 이미지와 `server` 코드를 사용하고 명령만 다르게 실행한다. `db`는 PostgreSQL 18과 pgvector 0.8.6을 제공한다.

지도 공개 버전 준비, 모델 작업 재시도와 publication 상태는 애플리케이션과 데이터베이스가 관리한다. 별도 queue service는 실제 동시 처리량이나 작업 분배 요구가 확인되기 전에는 추가하지 않는다.

## LangChain provider 경계

모델 호출 코드는 LangChain의 공통 생성 함수와 인터페이스를 사용한다. chat model은 `init_chat_model("provider:model")`, embedding model은 `init_embeddings("provider:model")` 형태로 구성하며, provider 전용 모델 클래스를 애플리케이션 경계 밖으로 노출하지 않는다.

최초 provider는 OpenAI이며 `langchain-openai`만 설치한다. 다른 provider로 전환할 때 해당 `langchain-<provider>` integration을 그 변경에서 추가하고 기존 integration의 필요성을 다시 판단한다. 자동 fallback, 여러 provider의 동시 routing이나 통합 과금이 실제 요구가 되기 전에는 OpenRouter나 LiteLLM 같은 gateway를 두지 않는다.

모델 작업은 정해진 Pydantic schema를 `with_structured_output()`에 전달하고 직접 모델을 호출한다. 현재 작업은 도구 호출이 필요하지 않으므로 LangChain agent abstraction을 사용하지 않는다.

모델과 provider library의 내부 재시도는 `max_retries=0`으로 끈다. 최초 호출, 즉시 재시도 1회, 1시간·2시간·4시간 간격 재시도 3회로 구성된 최대 5회의 애플리케이션 재시도만 호출 이력과 실패 유형을 기록한다.

`provider:model` 문자열은 모델 작업의 버전과 cache key에 포함한다. provider나 model이 바뀌면 해당 cache를 재사용하지 않는다.

embedding interface는 공통화하더라도 서로 다른 embedding model의 벡터 공간을 섞지 않는다. provider나 model을 바꾸면 영향받는 embedding을 전부 다시 만들고 새 공개 버전이 READY가 된 뒤 전환한다. 차원이 달라지면 먼저 승인된 데이터베이스 migration과 저장 구조가 필요하다. 최초 embedding model과 차원은 축약 스키마와 검색 품질 평가 이후 결정한다.

## 환경 변수와 비밀 관리

향후 저장소 루트에 값이 없는 `.env.example`을 추적하고 실제 `.env`와 파생 환경 파일은 `.gitignore`에 포함한다. Compose는 각 서비스에 필요한 변수만 주입한다.

- `CHAT_MODEL=openai:<model>`은 chat model을 지정한다.
- `EMBEDDING_MODEL=openai:<model>`은 embedding model을 지정한다.
- provider API key와 데이터베이스 자격 증명은 server와 worker에만 전달한다.
- `VITE_*` 변수에는 브라우저에 공개되어도 되는 값만 둔다.
- Pydantic settings는 필수 설정이 없으면 시작 단계에서 실패하고 로그에는 비밀 값을 출력하지 않는다.

`.env.example`, `.gitignore`와 Compose 파일은 코드 작업이 승인될 때 함께 만들며, 이 문서 작업에서는 생성하지 않는다.

## 버전과 lockfile 정책

`package.json`과 `pyproject.toml`의 직접 의존성은 이 문서의 정확한 버전으로 고정한다. `package-lock.json`과 `uv.lock`은 생성 시점부터 커밋하며, 전이 의존성 버전은 lockfile로만 관리한다.

버전 갱신은 별도 Issue와 검증을 거친 변경으로 처리한다. 사용하지 않는 provider integration이나 미래 확장을 위한 의존성은 미리 추가하지 않는다. 실제 설치 시 Python 3.14 지원 여부를 lock과 테스트로 확인하며, 호환되지 않는 직접 의존성이 있으면 런타임을 임의로 낮추지 않고 해당 결정부터 다시 승인받는다.

## CI 기준

CI workflow는 애플리케이션 골격을 만들 때 추가한다. 각 단계의 정확한 명령 이름은 실제 manifest와 함께 Issue #8에서 확정한다.

| 대상 | 필수 단계 |
| --- | --- |
| web | `npm ci`, Biome 포맷·lint 검사, TypeScript typecheck, Vitest, Vite build |
| server | `uv sync --frozen`, Ruff 포맷·lint 검사, mypy, pytest |
| 데이터베이스 통합 | PostgreSQL 18과 pgvector 0.8.6 기동, migration 적용, 핵심 DB integration test |

브라우저 E2E와 클라우드 배포 workflow는 POC 기준에 포함하지 않는다. 테스트가 10분을 넘는 전체 검증으로 커지면 실행 범위와 비용을 별도로 합의한다.

## 보류한 결정

- 축약 스키마, 제약과 실제 migration 설계
- OpenAI chat model의 정확한 ID
- embedding model, 차원과 벡터 컬럼 설계
- 그래프 시각화 후보의 최종 선택
- 실제 시작·검사·테스트 명령 이름
- 인증, 배포 환경과 운영 인프라

이 항목은 현재 사용자 흐름이나 승인된 스키마로 필요성이 확인된 뒤 결정한다. 미래 확장 가능성만으로 구조나 의존성을 추가하지 않는다.

## 확인 출처

버전은 2026-09-01에 각 프로젝트의 공식 배포 정보와 공개 package registry에서 확인했다.

- [Node.js v24.20.0 archive](https://nodejs.org/en/download/archive/v24.20.0)
- [Python release documentation](https://www.python.org/doc/versions/)
- [uv releases](https://github.com/astral-sh/uv/releases)
- [PostgreSQL release notes](https://www.postgresql.org/docs/release/)
- [pgvector releases](https://github.com/pgvector/pgvector/releases)
- [npm registry](https://www.npmjs.com/)
- [Python Package Index](https://pypi.org/)
- [LangChain providers and models](https://docs.langchain.com/oss/python/concepts/providers-and-models)
- [LangChain model interface and structured output](https://docs.langchain.com/oss/python/langchain/models)
- [LangChain embedding integrations](https://docs.langchain.com/oss/python/integrations/embeddings)
