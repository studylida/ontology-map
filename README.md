# ontology-map

ontology-map은 공개 자료에서 확인한 근거와 시간축을 지식그래프로 축적하고, 사용자가 선택한 node를 중심으로 동적 부분 graph를 탐색하는 웹 애플리케이션이다. 브라우저와 PostgreSQL 사이의 유일한 제품 경계는 FastAPI HTTP API다.

## 처음 읽을 문서

1. [HANDOFF.md](HANDOFF.md)에서 최신 `main`, 구현 상태와 다음 Issue를 확인한다.
2. [DESIGN.md](DESIGN.md)에서 제품과 화면 계약을 확인한다.
3. [logical-data-schema.md](logical-data-schema.md)와 [physical-data-schema.md](physical-data-schema.md)에서 frozen 데이터 의미와 PostgreSQL 계약을 확인한다.
4. [implementation-stack.md](implementation-stack.md)와 [code-conventions.md](code-conventions.md)에서 실제 구조, 버전과 코드 경계를 확인한다.
5. 변경을 시작하기 전에 [CONTRIBUTING.md](CONTRIBUTING.md)를 읽는다.

## 저장소 구조

| 경로 | 역할 |
| --- | --- |
| `web/` | React와 Vite 기반 사용자 화면, FastAPI adapter와 component test |
| `server/` | FastAPI HTTP 경계, application-service 함수, SQLAlchemy query, Alembic migration과 개발용 fixture |
| `compose.yaml` | 개발용 PostgreSQL과 FastAPI 컨테이너 |

PostgreSQL, migration, 개발용 HBF fixture, FastAPI, web과 종료·초기화 절차는 [database-operations.md](database-operations.md)에 모아 두었다. agent/worker는 아직 실행 가능한 구현과 명령이 없으며, 현재 상태와 후속 Issue는 [HANDOFF.md](HANDOFF.md)에서 확인한다.

## 문서 역할

- [DESIGN.md](DESIGN.md): 제품 의미, 상호작용과 시각 계약
- [implementation-stack.md](implementation-stack.md): 현재 런타임, 의존성, 프로세스와 코드 구조
- [logical-data-schema.md](logical-data-schema.md): frozen 논리 데이터 의미와 수명주기
- [physical-data-schema.md](physical-data-schema.md): frozen PostgreSQL 매핑, 무결성과 migration 기준
- [database-operations.md](database-operations.md): 로컬 실행과 DB 운영
- [code-conventions.md](code-conventions.md): TypeScript, Python, 테스트와 오류 처리 규칙
- [CONTRIBUTING.md](CONTRIBUTING.md): Issue, branch, commit, PR과 병합 규칙

현재 구현 범위나 다음 작업이 바뀌면 정식 문서를 중복해서 늘리지 않고 위 문서와 임시 [HANDOFF.md](HANDOFF.md)를 갱신한다.
