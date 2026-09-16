# #139 원문 보존형 추출 비교 공개 검토 자료

이 자료는 ontology-map [#139](https://github.com/studylida/ontology-map/issues/139)에서 수행한 원문 보존형 한국어 지식 추출 비교를 WEB GPT 6 Pro가 읽기 전용으로 검토할 수 있게 정리한 공개 패킷이다. 제품 구현이나 정식 계약이 아니며, 이 branch를 병합하기 위한 자료도 아니다.

## 결론과 현재 경계

기존 R7 prompt에 [원문 보존 문구](preserve-addendum.txt)만 추가한 조건은 엄격 통과율이 42.2%에서 57.8%로 높아졌고, 계약 실패를 제외한 짝비교에서도 개선 11건·회귀 1건·동률 40건이었다. 그러나 두 조건 모두 기사 한 번의 네 평가 단위를 모두 통과한 경우가 0/16이므로, 원문 보존 문구를 다음 비교 후보로 유지할 근거만 얻었을 뿐 제품 worker·자동 저장·운영 품질을 승인하지 않았다.

## 시험 설계

| 항목 | 내용 |
| --- | --- |
| 대상 | 이전 개발 자료와 URL·문서 hash가 겹치지 않는 공식 한국어 기사 8건과 사건군 8개 |
| 비교 조건 | 동결된 R7 prompt / 같은 prompt에 원문 보존 문구만 추가 |
| 호출 | 기사별 2조건 × 2반복, 총 32회 |
| 평가 단위 | 기사마다 사전 지정한 문장·표 행 4개, 조건과 반복을 합쳐 128개 평가 항목 |
| 모델 | `qwen3.7-flash-2026-07-15`, temperature 0, thinking·streaming 비활성, 최대 출력 3,000 token |
| 평가 | 출력 전에 동결한 gold를 사용해 조건명을 숨긴 단일 검토자가 `PASS`·`PARTIAL`·`FAIL`·`CONTRACT_ERROR`로 판정 |
| 비용 | 이번 비교 $0.01267030, 이전 사용량·불명확 예약 포함 누적 $0.86442523 |

128개는 독립 표본 수가 아니라 조건·반복을 포함한 평가 항목 수다. 독립 원문은 8건이며 목적 표집이므로 통계적 일반화나 운영 성능을 주장하지 않는다. 계약 실패 3회는 자동 수정·재호출하지 않았고 실패율과 비용에 포함했다.

## 자료 지도

| 파일 | 확인할 수 있는 내용 |
| --- | --- |
| [REPORT.md](REPORT.md) | 결과, 개선·회귀, 한계와 다음 후보 요약 |
| [manifest.json](manifest.json) | 사전 고정 설정, 호출 상한, 중단 규칙, 요청 hash와 의존 파일 hash |
| [preserve-addendum.txt](preserve-addendum.txt) | 비교에서 유일하게 추가한 작성 지침 |
| [gold.json](gold.json) | 출력 전에 동결한 평가 단위와 필수 의미의 요약 표현 |
| [blind-review.json](blind-review.json) | 조건명을 가린 128개 수동 판정과 짧은 사유 |
| [blind-map.json](blind-map.json) | 판정 동결 뒤 공개한 후보 번호와 조건의 대응 |
| [score.json](score.json) | 조건별·기사별·짝비교 집계와 해석 경계 |
| [source-index.json](source-index.json) | 공식 원문 URL, 게시자, 문서 hash, 문자 수와 원문 단위 수. 기사 전문은 제외 |
| [call-metadata.json](call-metadata.json) | 출력 본문을 제외한 요청 hash, 모델 설정, token·비용·종료·계약 오류 메타데이터 |
| [REVIEW_PROMPT.md](REVIEW_PROMPT.md) | WEB GPT 6 Pro에 전달할 독립 검토 요청 |

## 공개하지 않은 자료와 확인 한계

저작권이 있는 기사 전문, 모델의 원응답·추론 기록, API 키, workspace host와 개인 설정은 이 branch에 싣지 않았다. 공개 자료는 실험 설계, 고정 여부, 집계, 평가 판정과 비용을 감사하는 데 사용할 수 있지만 모델 출력과 원문을 직접 대조하는 완전한 의미 재채점에는 충분하지 않다. 공식 기사 URL은 제공하되, 공개하지 않은 모델 출력의 의미를 추정해 새 점수로 만들지 않는다.

`gold.json`의 필수 의미는 원문의 짧은 직접 인용이 아니라 검토용 요약이다. `blind-review.json`의 사유도 모델 원응답이 아니라 수동 판정 기록이다. hash는 자료의 동일성만 보조하며 의미 정확성을 증명하지 않는다.

## 현재 판단과 다음 후보

원문 보존 문구는 다음 후보로 유지하되 이 8건은 이후 회귀 자료로 전환한다. 다음 단일축 후보는 문장 ID와 정확한 원문 slice를 유지하면서 발언·지시어가 이어지는 단위를 runtime에서 함께 제공하는 방식이다. 이는 실행 중 입력 구성의 후보이며 DB schema·Observation 단위·영속 계약 변경이 아니다.

Flash의 엄격한 Structured Output 지원 여부는 의미 품질 시험과 분리한 소규모 호환성 확인 대상으로 남긴다. Atomicity 입력 축소와 표 구조 보조 뷰는 이번 비교에서 확인된 주 병목이 아니므로 계속 보류한다.

Issue의 공식 결과는 [#139 결과 댓글](https://github.com/studylida/ontology-map/issues/139#issuecomment-5593857725)과 [#127 경계 댓글](https://github.com/studylida/ontology-map/issues/127#issuecomment-5593861040)에서 확인한다. 현재 제품 계약은 저장소의 정식 문서와 병합된 코드를 따르며, 이 공개 패킷이 제품 계약을 바꾸지 않는다.
