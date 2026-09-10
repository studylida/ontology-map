# ontology-map #131 수집 인계

> 확인일: 2026-09-10. 작업 기준은 `main`의 `9a42d94fac3406de3a3a582d224f109744b65558`이며, 이후 상태는 GitHub와 실제 commit을 다시 확인한다.

## 검증된 결과

- [#131](https://github.com/studylida/ontology-map/issues/131)의 일회성 시연 corpus를 `2026-06-11T00:00:00Z <= published_at < 2026-09-09T00:00:00Z` 범위에서 만들었다. GDELT 후보 6,640행을 canonical URL 기준 6,513개로 병합하고, 실제 한국어 본문 1,000건을 선택했다.
- 공개 snapshot ID는 `6db4f34db3fa7573`이다. 결과·분포·BigQuery 작업 ID·재현 명령은 [수집 결과](review/131-gdelt-collection/README.md), 공개 레코드는 [manifest](review/131-gdelt-collection/manifest.jsonl), 수동 판단은 [감사 결과](review/131-gdelt-collection/audit.csv)에 있다.
- 최종 1,000건의 canonical URL과 본문 SHA-256은 각각 모두 고유하고 제목 공백은 없다. 삼성전자·Intel·NVIDIA와 SK하이닉스가 같은 원문 맥락에 있는 예약 자료는 기업별 3건씩이다.
- 고정 표본 100건을 실제 본문으로 확인한 결과 발행일·한국어·본문 추출은 각각 100/100, 직접 관련성은 94/100, 파트너 맥락은 9/9였다. 개발 fixture나 모델 산출물의 품질 검증 결과가 아니다.

## 외부 보관과 범위

- 후보 CSV, 원문 gzip, 수집 checkpoint와 private audit 원본은 Git 저장소 밖 접근 제한 경로 `~/.local/share/ontology-map/gdelt/2026-06-11_2026-09-09`에 있다. 공개 manifest의 `artifact_key`가 원문을 가리키며 대량 원문은 Git·Issue·PR에 게시하지 않는다.
- 게시일 메타데이터 생략과 제목 누락을 발견한 이전 실행 기록은 같은 외부 경로의 `failed-smoke-metadata-disabled`와 `failed-full-missing-title`에 보존했다. 최종 snapshot은 두 결함을 수정한 새 checkpoint에서 생성했다.
- 이 수집기는 다음 시연을 위한 고정 범위 일회성 도구다. 운영 수집 platform, scheduler, 제품 API·DB 적재, schema·migration, Agent·모델 호출은 추가하지 않았다. 향후 제품 입력은 다른 주체가 모집·제공한 자료를 받는다.

## 다음 작업

- 사용자가 지정한 다음 작업은 [#110](https://github.com/studylida/ontology-map/issues/110)이다. #131 자료를 대표 예시로 사용해 허용 자료, lint 적용 대상, 원문에서 Evidence Trace까지의 적재·publication 정책을 정하되 수집기나 적재 코드를 구현하는 Issue로 바꾸지 않는다.
- [#111](https://github.com/studylida/ontology-map/issues/111)은 #131의 검증 자료 중 작은 집합을 본문 추출 Agent 입력 경계로 넘긴다. #111은 #110·#64·#124에 의존하므로 최신 결정과 선행 상태를 다시 확인한다.
- #110 이후에도 #127의 지식 후보 작성, #128의 Node 동일 대상 판정, 실제 저장·publication 구현은 각각의 승인 범위로 남긴다. #68·#129의 생성 작업과 #139의 추가 모델 시험을 이번 결과로 재개하지 않는다.
