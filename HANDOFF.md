# ontology-map 문서 정합화 인계

> 확인일: 2026-09-08. 문서 작업 기준은 `main`의 `ffbca386a875b517137412d385b3eea36719521e`다. 이후 상태는 GitHub와 실제 commit을 다시 확인한다.

- 문서 정합화는 [#158](https://github.com/studylida/ontology-map/issues/158), 전용 WSL worktree `docs-158-stack-decisions`, branch `docs/158-stack-decisions`에서 진행한다. 근거별 반영 위치와 검증·PR은 #158에 남긴다.
- 프론트엔드 선행 PR과 #157은 위 main에 병합됐다. 기본 디자인·사람 노드 주황색·이름 표시 시점, 실제 3단계 탐색·주변부 조회·관계 경로·저장 인사이트 읽기를 현재 구현으로 확인했다. 이전 미병합 stack·미리보기 채택 대기 설명은 더 이상 현재 상태가 아니다.
- 현재 기술·모델 구성은 [구현 스택](docs/development/implementation-stack.md), 화면·선정 원칙은 [제품 설계](docs/product/design.md), 실행·합성 fixture는 [DB 운영](docs/operations/database.md)을 따른다. 반복되는 현재 계약을 이 인계에 복사하지 않는다.
- 사용자 지정 세션 `01a07f95-85b2-7c82-b144-5f089b8b9e95`의 병합 결과와 `01a07e4a-f385-7331-8f7c-8c78f4bddfb7`의 에이전트 시험·정정·후속 승인 근거를 #158에서 대조한다. 병합 후 승인된 상세 정보·이름·강조 개선은 #159의 별도 작업이며 현재 화면과 구별한다. 중심 복귀 버튼 등 미승인 제안을 구현 범위로 넣지 않는다.
- #139는 별도 세션이 맡는다. R8 이후 평가 정리·Composer 효용·정답표 없는 검증·표 구조 지원 비교가 승인됐으며 상세 실행·예산·결과는 해당 Issue를 확인한다. 이 문서 작업은 시험을 재개하거나 제품 Agent 개수·모델·task kind를 확정하지 않는다.
- 제품 추출·판정·저장·publication worker, 질문 생성과 인사이트 생성·품질은 미완료다. 저장 읽기·합성 fixture와 모델 실험을 실제 데이터 E2E 완료로 처리하지 않는다. #124~#130, #68과 연결된 입력·수집 Issue를 확인한다.
- #121의 pgvector 제거와 #117의 검색 변경은 문서 기준 commit에 미적용이다. 공통 READY basis 검증 gap은 #120, 누적 page·cache 경계는 #136에서 확인한다. 이미 승인된 독립 작업만 진행하고 미결정 계약을 임의로 구현하지 않는다.
- #158은 문서와 Issue 근거만 변경한다. 배포·tag·release와 이번 문서 PR의 병합은 수행하지 않는다. 기존 worktree·세션 기록·시험 자료·다른 세션의 변경은 보존한다.
