# ontology-map frontend 통합 인계

> 확인 시점: 2026-09-08. 이 문서는 현재 작업 인계용이며 제품·데이터 계약은 README에서 안내하는 정식 문서를 따른다.

- 확인한 기본 브랜치: `main`과 `origin/main` 모두 `b446b21252fe45afe1f1a1379cf7272555350ecb`다.
- 현재 frontend 통합의 승인 범위·제약·미완료 판단은 [상위 Issue #147](https://github.com/studylida/ontology-map/issues/147)에서 추적한다. 작업 위치는 WSL `feat-frontend-until139`이며 별도 에이전트 구현 작업과 경로를 겹치지 않는다.
- 기존 Draft stack은 PR #140~#146이다. 이번 후속은 개발 검토 fixture `cab143c`(#149), 전환 후 위치 고정 `7d2649a`(#150), node·HTML label 확대 `c60d9b8`(#151), 실제 3단계·주변부 조회 `30c1698`(#152), 관계 경로 `7f8c851`(#153) 순서다. 인사이트 읽기·탭 복원은 이 인계본과 같은 PR에서 이어진다.
- 관련 web 검사와 실제 DB 기반 exploration·Relation·peripheral·인사이트 검사를 진행했다. 최종 검증 증거와 PR 링크는 #147과 각 하위 Issue에 기록한다. 가상 검토 자료는 모델의 결과 품질이나 실제 사실의 증거가 아니다.
- 다음 작업은 #106/#114/#134의 사용자 화면 확인과 #136의 누적 page 관찰 결과 검토다. 구현·에이전트 검증과 사용자 기능 완료를 구분하고 필요한 확인이 남으면 Issue와 Draft를 열어 둔다.
- 인사이트 생성 worker, 질문 생성·prompt 변경, #131 수집, #132 전체 감사, #117/#121 검색 변경, 별도 node Claim 화면, DB schema 변경은 이번 실행 범위가 아니다. cache·거리 기반 제거는 관찰 후 별도 승인 전까지 구현하지 않는다.
- DB·API·web 실행과 별도 100-node 검토 자료의 적재 방법은 [DB 운영 문서](docs/operations/database.md)를 따른다. `/mnt/c`에서 Vite가 변경을 감지하지 못하면 같은 문서의 polling 실행 방법을 사용한다.
- 병합·배포·tag·release는 수행하지 않았다. 기존 worktree와 다른 세션의 변경을 이동하거나 폐기하지 않는다.
