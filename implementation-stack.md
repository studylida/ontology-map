# ontology-map 구현 스택 기준

## 문서 상태

- 상태: 승인된 구현 기준
- 확인일: 2026-09-01
- 관련 Issue: #38
- 코드 컨벤션: [code-conventions.md](code-conventions.md)

이 문서는 Logical Schema v1 동결 이후 적용할 ontology-map의 구현 스택, 현재 프론트엔드 POC, 목표 폴더 구조, 환경 변수, 실행 프로세스와 CI 기준을 기록한다. `web/`에는 Issue #67의 실행 가능한 desktop POC와 프론트엔드 의존성이 있다. 백엔드, 물리 스키마, Compose와 운영 환경은 아직 없으며 각각의 후속 Issue와 승인을 거쳐 만든다.

## 기본 원칙

- 하나의 저장소에서 TypeScript 프론트엔드와 Python 백엔드·에이전트를 관리한다.
- 로컬 실행은 Docker Compose를 기준으로 하되, API와 worker는 같은 Python 코드와 이미지를 사용하고 실행 명령만 구분한다.
- POC에는 인증, 클라우드 배포, 브라우저 E2E, 자동 모델 fallback과 통합 모델 gateway를 도입하지 않는다.
- 직접 의존성은 정확한 버전으로 고정하고, 사용하지 않는 provider integration은 설치하지 않는다.
- 데이터베이스 구조와 migration은 Logical Schema v1을 바꾸지 않으며, Issue #40부터 시작하는 별도 PostgreSQL 물리 설계와 구현 Issue에서 다룬다.

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
| 그래프 시각화 POC | 3d-force-graph | 1.80.0 |
| 3D 렌더링 | Three.js | 0.185.0 |
| 포맷·lint | Biome | 2.5.11 |
| 단위·컴포넌트 테스트 | Vitest | 4.1.11 |
| React 테스트 유틸리티 | React Testing Library | 16.3.3 |

Issue #67의 POC는 3d-force-graph를 채택했고 Reagraph는 설치하지 않았다. 3d-force-graph가 제공하는 Three.js 객체 확장 지점을 사용하므로 Three.js를 직접 의존성으로 함께 고정한다. 다른 그래프 라이브러리는 현재 요구를 충족하지 못한다는 검증 결과가 생길 때만 다시 비교한다.

시각 POC는 `nodeThreeObject`, `lights`와 `postProcessingComposer`를 사용해 node 재질, 제한된 bloom과 거리 안개를 표현한다. x·y 배치를 주된 구조로 유지하면서 사용자 정의 force로 z축을 약 ±32 안에 제한하고 회전 control은 끈다. 각 node의 런타임 depth target은 node ID에서 계산하되 relation 단계나 강도와 연결하지 않고 저장하지도 않는다. 모든 관계선은 `linkThreeObject`와 `linkPositionUpdate`로 직접 그린다. 각 필라멘트는 source와 target의 중심에서 시작하고 중간 control point만 벌어지며 충돌 관계에는 `LineDashedMaterial`을 사용한다. node 아래에는 배경색의 불투명 가림 glyph를 두고 node 표면과 label에 관계선보다 높은 `renderOrder`를 적용해 선이 node 위에 보이지 않게 한다.

관계선의 기본 불투명도는 직접 이웃 0.90, 중요한 2단계 이웃 0.56, 주변부 실제 Relation 0.30으로 둔다. 독립 근거 묶음 수만큼 같은 경로에 1px 필라멘트를 겹쳐 그린다. 5개까지는 중간 control point 간격을 1.2px로 유지하고 5개를 넘으면 전체 폭을 4.8px로 고정한 채 간격만 줄인다. 단계별 대비에는 색과 불투명도만 사용하고 근거 강도는 필라멘트 수만 나타낸다.

node 크기는 선택 기간에 게시된 출처가 뒷받침하는 Claim의 독립 근거 묶음 수를 나타낸다. 중심 node는 가장 밝게 유지하고 직접 이웃과 중요한 2단계 이웃은 같은 기본 밝기와 불투명도를 사용하며 주변부만 낮춘다. 오래됨은 지도의 시각 채널로 사용하지 않고 상세 panel의 근거 게시일과 Evidence Trace에서 제공한다.

node를 선택하면 같은 node와 Relation 객체를 유지한 채 1200ms ease-in-out으로 카메라 target, node 재질과 관계선 불투명도를 보간하고 force를 한 번 다시 시작한다. header, URL, 탐색 경로와 상세 panel의 중심 상태는 전환이 끝날 때 갱신한다. hover·focus는 160ms 동안 node halo와 직접 연결된 관계선을 함께 강조하고, 시간 범위에 따른 node 크기는 320ms 동안 전환한다.

검증 fixture는 작은 전체 node catalog를 브라우저에 두고 선택한 중심의 직접 이웃과 2단계 이웃을 계산한다. 나머지 공개 node는 주변부로 분류하되 실제 Relation만 유지하고, Relation이 없는 node나 검색 결과에 새 관계선을 만들지 않는다. 제품 조회에서는 Logical Schema v1에 따라 중심 1개, 직접 이웃 최대 12개, 중요한 2단계 이웃 최대 18개와 관계선 최대 60개를 결정적으로 선택한다.

현재 POC는 모든 fixture node와 Relation 객체를 처음 한 번 만들고 중심이 바뀔 때 같은 객체의 탐색 단계를 갱신한다. `warmupTicks`와 `cooldownTicks`는 각각 180이고 `d3AlphaDecay`는 0.035, `d3VelocityDecay`는 0.4다.

제품에서는 현재 경계 node ID를 cursor로 사용해 다음 주변부를 제한된 page 단위로 요청하고, camera가 경계에 접근하거나 주변부 node가 focus되면 다음 page를 미리 불러온다. 멀어진 주변부는 `graphData`와 force 계산에서 제외하고 세션 위치 cache만 유지한다. 임의의 node 1,000개를 초기 graph에 넣거나 서버에 저장된 좌표로 viewport를 조회하지 않는다. 주변부 규모가 커지면 먼저 `nodeVisibility`와 `linkVisibility`로 장면 범위를 제한하고, 같은 형상의 주변부 node는 Three.js `InstancedMesh`나 sprite 기반 표현을 성능 POC에서 비교한다.

검색 input은 combobox와 listbox 패턴을 사용한다. 입력값이 바뀌면 이름, 유형과 검색 이유를 포함한 후보를 최대 5개까지 드롭다운으로 표시하고, `ArrowUp`·`ArrowDown`·`Enter`·`Escape`와 pointer 선택을 지원한다. 후보 선택은 별도 모델 호출 없이 기존 중심 이동 함수를 사용한다.

제품에서 서버가 부분 graph를 교체하게 되면 이전 graph와 새 graph의 합집합을 한 번 `graphData`에 전달하고 `d3ReheatSimulation`도 한 번만 호출한다. 공통 node·관계선 객체와 Three.js 재질은 cache에서 재사용하고 진입 요소와 이탈 요소는 `DESIGN.md`의 전환 계약에 따라 보간한다. 이 서버 연동과 부분 graph paging은 현재 정적 fixture POC에 포함되지 않는다.

POC의 기본 밀도는 활성 node의 charge strength -64, 직접 이웃 link distance 56, 2단계 이웃 link distance 46을 시작값으로 사용한다. 기본 카메라 배율에서 직접 이웃과 중요한 2단계 이웃을 함께 찾을 수 있는지를 우선 검증하며, node와 label이 겹치면 간격만 필요한 만큼 늘린다.

홈페이지 첫 진입에서는 graph force가 안정될 때까지 전체 viewport loading을 표시한다. 진행률은 1.4초 동안 89%까지 올리고 준비 신호 뒤 90%, 95%, 99%를 거쳐 200ms 동안 loading을 숨긴다. 그 뒤 전체 fixture graph를 `zoomToFit`으로 조망하고 720ms 동안 유지한 다음 1200ms 동안 카메라 target과 node 위치를 바꾸지 않고 카메라 거리만 줄인다. 검증 fixture에는 BISTelligence node가 없으므로 SK하이닉스를 기본 중심으로 사용하며 intro graph는 제품의 기준 지도나 저장 좌표로 보존하지 않는다. `enableNodeDrag(false)`로 node drag를 끄고 click은 중심 이동에만 사용하며 OrbitControls의 pan과 zoom은 계속 활성화한다.

상세 panel의 `인사이트` tab은 제목 목록만 표시하고 native `<dialog>`로 상세 demo를 연다. SK하이닉스, SanDisk와 HBF에 정적 인사이트를 각각 3개 제공하고 나머지 node에는 empty 상태를 표시한다. 이 데이터는 실제 모델 출력이 아니며 생성·저장·API 계약은 Issue #68에서 결정한다.

Next.js와 저장소 공통 패키지는 현재 필요하지 않으므로 만들지 않는다. 웹 앱은 Vite 기반의 단일 React 애플리케이션이며 반응형 화면, API, DB와 모델 호출은 Issue #67 POC 범위에 포함되지 않는다.

### 로컬 실행과 검증

`web/`에서 다음 명령을 사용한다.

```text
npm ci
npm run dev
npm run check
```

`npm run check`는 Biome 검사, TypeScript typecheck, Vitest와 Vite production build를 순서대로 실행한다. 브라우저 smoke check는 검색, node 선택, pan·zoom, Evidence Trace, 후속 질문, 인사이트 dialog와 첫 진입 확대를 확인한다.

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
- `server/migrations/`는 승인된 PostgreSQL 물리 설계를 구현하는 Alembic migration만 둔다.

초기에는 이보다 더 세분화된 layer, 공유 package나 추상화 폴더를 만들지 않는다. 코드가 생긴 뒤 실제 책임이 겹칠 때 [코드 컨벤션](code-conventions.md)에 따라 경계를 구체화한다.

## 실행 프로세스

향후 로컬 Compose는 `web`, `api`, `worker`, `db` 네 서비스를 제공한다. `api`와 `worker`는 같은 Python 이미지와 `server` 코드를 사용하고 명령만 다르게 실행한다. `db`는 PostgreSQL 18과 pgvector 0.8.6을 제공한다.

지도 공개 버전 준비, 모델 작업 재시도와 publication 상태는 애플리케이션과 데이터베이스가 관리한다. 별도 queue service는 실제 동시 처리량이나 작업 분배 요구가 확인되기 전에는 추가하지 않는다.

## LangChain provider 경계

모델 호출 코드는 LangChain의 공통 생성 함수와 인터페이스를 사용한다. chat model은 `init_chat_model("provider:model")`, embedding model은 `init_embeddings("provider:model")` 형태로 구성하며, provider 전용 모델 클래스를 애플리케이션 경계 밖으로 노출하지 않는다.

최초 provider는 OpenAI이며 `langchain-openai`만 설치한다. 다른 provider로 전환할 때 해당 `langchain-<provider>` integration을 그 변경에서 추가하고 기존 integration의 필요성을 다시 판단한다. 자동 fallback, 여러 provider의 동시 routing이나 통합 과금이 실제 요구가 되기 전에는 OpenRouter나 LiteLLM 같은 gateway를 두지 않는다.

모델 작업은 정해진 Pydantic schema를 `with_structured_output()`에 전달하고 직접 모델을 호출한다. 현재 작업은 도구 호출이 필요하지 않으므로 LangChain agent abstraction을 사용하지 않는다.

모델과 provider library의 내부 재시도는 `max_retries=0`으로 끈다. 최초 호출, 즉시 재시도 1회, 1시간·2시간·4시간 간격 재시도 3회로 구성된 최대 5회의 애플리케이션 재시도만 호출 이력과 실패 유형을 기록한다.

`provider:model` 문자열은 모델 작업의 버전과 cache key에 포함한다. provider나 model이 바뀌면 해당 cache를 재사용하지 않는다.

embedding interface는 공통화하더라도 서로 다른 embedding model의 벡터 공간을 섞지 않는다. provider나 model을 바꾸면 영향받는 embedding을 전부 다시 만들고 새 공개 버전이 READY가 된 뒤 전환한다. 차원이 달라지면 먼저 승인된 데이터베이스 migration과 저장 구조가 필요하다. 최초 embedding model과 차원은 검색 품질 평가와 별도 물리 설계 결정을 거쳐 확정한다.

## 환경 변수와 비밀 관리

향후 저장소 루트에 값이 없는 `.env.example`을 추적하고 실제 `.env`와 파생 환경 파일은 `.gitignore`에 포함한다. Compose는 각 서비스에 필요한 변수만 주입한다.

- `CHAT_MODEL=openai:<model>`은 chat model을 지정한다.
- `EMBEDDING_MODEL=openai:<model>`은 embedding model을 지정한다.
- provider API key와 데이터베이스 자격 증명은 server와 worker에만 전달한다.
- `VITE_*` 변수에는 브라우저에 공개되어도 되는 값만 둔다.
- Pydantic settings는 필수 설정이 없으면 시작 단계에서 실패하고 로그에는 비밀 값을 출력하지 않는다.

`.gitignore`는 Issue #39에서 별도로 관리한다. `.env.example`과 Compose 파일은 애플리케이션 골격을 만드는 Issue에서 실제 설정 계약과 함께 추가한다.

## 버전과 lockfile 정책

`package.json`과 `pyproject.toml`의 직접 의존성은 이 문서의 정확한 버전으로 고정한다. `package-lock.json`과 `uv.lock`은 생성 시점부터 커밋하며, 전이 의존성 버전은 lockfile로만 관리한다.

버전 갱신은 별도 Issue와 검증을 거친 변경으로 처리한다. 사용하지 않는 provider integration이나 미래 확장을 위한 의존성은 미리 추가하지 않는다. 실제 설치 시 Python 3.14 지원 여부를 lock과 테스트로 확인하며, 호환되지 않는 직접 의존성이 있으면 런타임을 임의로 낮추지 않고 해당 결정부터 다시 승인받는다.

## CI 기준

`web/package.json`에는 아래 검증 script가 구현되어 있다. CI workflow는 아직 없으며 추가할 때 같은 명령 계약을 사용한다. server와 데이터베이스 단계는 해당 애플리케이션과 migration이 생긴 뒤 추가한다.

| 대상 | 필수 단계 |
| --- | --- |
| web | `npm ci`, Biome 포맷·lint 검사, TypeScript typecheck, Vitest, Vite build |
| server | `uv sync --frozen`, Ruff 포맷·lint 검사, mypy, pytest |
| 데이터베이스 통합 | PostgreSQL 18과 pgvector 0.8.6 기동, migration 적용, 핵심 DB integration test |

브라우저 E2E와 클라우드 배포 workflow는 POC 기준에 포함하지 않는다. 테스트가 10분을 넘는 전체 검증으로 커지면 실행 범위와 비용을 별도로 합의한다.

## 보류한 결정

- PostgreSQL 물리 스키마, 제약과 실제 migration 설계
- OpenAI chat model의 정확한 ID
- embedding model, 차원과 벡터 컬럼 설계
- 목표 desktop에서의 주변부 page 크기와 장면 상한
- 실제 인사이트의 출력 구조, 생성·저장 시점과 Evidence Trace 연결
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
