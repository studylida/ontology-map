# #139 Flash·Plus 생성 비교 공개 검토 자료

이 자료는 ontology-map [#139](https://github.com/studylida/ontology-map/issues/139)의 원문 보존형 최소 추출에서 Flash와 Plus의 생성 품질을 비교한 공개 검토 패킷이다. 제품 구현이나 정식 출력 계약이 아니며, 자동 저장과 운영 품질을 승인하지 않는다.

## 결론

동결한 후보 유지 기준을 모두 만족한 모델은 없다. Flash는 필수 사실 엄격 통과율이 `32/48(66.67%)`로 Plus의 `18/48(37.50%)`보다 높았지만, 행동 주체를 바꾸는 중대 오류가 같은 사실의 두 반복에서 재현됐고 Claim 근거 실패율도 더 높았다. Plus는 해당 중대 오류와 근거 실패를 줄였지만 필수 사실 보존과 유효 지식 산출량이 크게 낮았다.

따라서 Flash 또는 Plus를 제품 생성 모델로 선택하지 않고, prompt 예외 추가·repair·자동 재호출·데모 입력 기능 구현도 진행하지 않는다. 이 네 기사는 이후 개발·회귀 자료로만 사용한다.

## 시험 설계

| 항목 | 내용 |
| --- | --- |
| 대상 | 이전 #139 자료와 URL·문서 hash·사건군이 겹치지 않는 공식 한국어 기사 4건 |
| 비교 축 | 모델 snapshot만 Flash와 Plus로 변경 |
| 고정 조건 | 같은 평탄화 기사 입력, 원문 보존 prompt, `statement + modality + source_ids`, strict JSON Schema, temperature 0, thinking·streaming 비활성, 최대 출력 6,000 tokens |
| 호출 | 4기사 × 2모델 × 2반복, 총 16회 |
| 사전 gold | 기사마다 필수 사실 6개, 총 24개 |
| 평가 | 모델 조건을 숨긴 뒤 각 Claim의 자기 근거와 네 품질 축을 검토하고, 유효 Claim 집합으로 필수 사실을 판정 |
| 비용 | 사전 예약 `$0.144587 / $0.30`, 실제 추정 `$0.03756943` |

16회는 독립 자료 수가 아니다. 독립 원문·사건군은 4개이고, 모델별 필수 사실 48개는 24개 사실의 두 반복이다. 목적 표집된 작은 자료이므로 일반적인 한국어 추출 성능이나 운영 품질로 확대 해석하지 않는다.

## 자료 지도

| 파일 | 내용 |
| --- | --- |
| [REPORT.md](REPORT.md) | 결과, 기준별 판정과 다음 경계 |
| [manifest.json](manifest.json) | 사전 설정, 비용 예약, 후보 유지 기준과 중단 규칙 |
| [input-contract.json](input-contract.json) | 고정한 prompt·출력 계약·호출 설정 |
| [gold.json](gold.json) | 출력 전 동결한 필수 의미·modality·근거 조합 |
| [blind-review.json](blind-review.json) | 조건 공개 전 동결한 96개 사실 판정과 501개 Claim 다축 판정 |
| [blind-map.json](blind-map.json) | 판정 동결 뒤 공개한 후보 번호와 모델 대응 |
| [score.json](score.json) | 모델별·기사별·짝비교 집계와 후보 판정 |
| [source-index.json](source-index.json) | 원문 URL·게시자·hash·문자 수·원문 단위 수 |
| [call-metadata.json](call-metadata.json) | 출력 본문을 제외한 호출·token·비용·종료 메타데이터 |
| [ledger.json](ledger.json) | 이번 라운드 비용 원장 |
| [REVIEW_PROMPT.md](REVIEW_PROMPT.md) | 외부 독립 검토 요청문 |

## 공개 범위와 한계

저작권이 있는 기사 전문, 모델 원응답, API 키, workspace host와 개인 설정은 공개하지 않는다. 공개 판정 원장에는 Claim 문장도 포함하지 않으므로 설계·집계·평가 경계는 감사할 수 있지만 원문과 생성문을 직접 대조한 의미 재채점은 할 수 없다.

평가자는 실험을 설계·실행한 Codex이며 독립적인 사람 평가자가 아니다. 모델명은 판정 원장에서 숨겼지만 호출 직후 Claim 개수 차이를 보았기 때문에 출력 형태로 조건을 추측할 가능성을 완전히 배제할 수 없다. 이 제한은 결과를 무효로 만들지는 않지만 독립 검증 결과로 부르지 않는다.

## 제품 경계

이번 결과는 새 table·column·task kind·publication pointer의 필요성을 만들지 않았다. 최종 Claim과 정확한 Observation 연결은 기존 frozen schema를 재사용할 수 있으며, 원응답·중간 후보·평가 gold와 판정 원장은 제품 DB에 저장하지 않는다.

승자가 없으므로 별도 데모 평가 관문과 URL·파일 입력 페이지 구현으로 넘어가지 않는다. `.docx`를 포함한 파일 입력 계약은 승인된 미래 범위로만 유지하며 Agent 후보가 품질 관문을 통과한 뒤 별도 Issue에서 다룬다.
