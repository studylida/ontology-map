# #139 인접 원문 ID 비교 검토 자료

이 패킷은 원문 보존 prompt를 고정한 상태에서 위치상 인접한 원문 ID 표시가 근거 연결을 개선하는지 비교한 목적 표집 시험을 재검토하기 위한 자료다. 기존 원문 보존형 결과와 점수는 수정하지 않았다.

## 포함 자료

- `REPORT.md`: 결과, 오류와 해석 범위
- `manifest.json`: 호출 전 동결한 조건·비용·요청 hash
- `gold.json`: 호출 전 동결한 필수 의미·근거 조합·modality
- `source-index.json`: 공식 URL, 본문 hash와 focus 목록
- `blind-review.json`, `blind-map.json`, `score.json`: 조건 가림 판정과 조건 공개 후 집계
- `call-metadata.json`: 원문·모델 출력이 제거된 호출 메타데이터
- `input-contract.json`: 두 조건의 유일한 입력 차이와 출력 schema
- `strict-score.json`, `strict-call-metadata.json`: 별도 strict JSON Schema 호환성 시험
- `snapshots/`: 시험 구성·판정·검사의 로컬 코드 사본

## 제외 자료

기사 전문, 모델 원응답·추론 기록, API 키, Workspace 주소와 개인 설정은 포함하지 않았다. `blind-review.json`의 판정자는 동결 gold를 사용한 Codex 한 명이며 독립적인 사람 검토나 운영 품질 평가가 아니다.

실행 전 동결 기록은 [Issue #139 댓글](https://github.com/studylida/ontology-map/issues/139#issuecomment-5594701965)에 있다. 이전 후보 검토 자료는 [`original-preserving-v1`](../original-preserving-v1/)에 있다.
