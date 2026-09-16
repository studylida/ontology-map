# ontology-map 개별 Claim 근거 경계 무호출 감사

이 패킷은 [#139](https://github.com/studylida/ontology-map/issues/139)의 기사 전체 최소 추출 진단을 모델 호출 없이 다시 감사한 결과다. 기존 `gold.json`, `review.json`, `score.json`과 `20/42` 점수는 수정하지 않고, 384개 Claim의 근거·modality·원자성·선정 판정과 42개 필수 사실의 유효 Claim 대응을 별도 버전으로 기록했다.

| 기준 | 값 |
| --- | --- |
| 감사 입력이 고정된 검토 branch commit | `43f89d63f65be903a2d6d305f2716542208795bc` |
| 감사 시작 시 최신 `origin/main` | `9a42d94fac3406de3a3a582d224f109744b65558` |
| 모델 호출 | 0회 |
| API 비용 | 0달러 |

## 결론

- 기존 동결 점수는 `20/42`이며 그대로 보존했다.
- M04-F06의 충분 근거를 `s20`으로 교정한 효과만 적용하면 `22/42`다.
- 개별 Claim이 자기 `source_ids`만으로 지원되는지 다시 적용하면 교정 전 `14/42`, 교정 후 `16/42`다.
- 384개 Claim 중 자기 근거 경계에서 원문 지원 FAIL은 93개, modality·귀속 FAIL은 24개, 원자성 FAIL은 6개, 선정 제외는 34개다. 축은 겹치므로 합산하지 않는다.
- 네 축을 모두 통과한 Claim은 240개다. 이 개수는 자동 저장 가능한 지식 수나 운영 정확도가 아니다.
- 현재의 `prompt + 평탄화된 기사 입력 + 최소 출력 schema + 6,000-token` 결합 구성은 품질 후보로 계속 기각한다. 최소 형식은 연구용 대조 형식으로만 남긴다.

## 파일 안내

| 파일 | 내용 |
| --- | --- |
| [REPORT.md](REPORT.md) | 감사 방법, 판정 변화, 의미, 한계와 다음 제안 |
| [PLAN.md](PLAN.md) | Issue에 먼저 기록한 감사 범위와 제외 범위 |
| [policy.json](policy.json) | Claim·필수 사실 판정 경계와 원본 hash |
| [gold-amendment.json](gold-amendment.json) | 원본을 덮어쓰지 않은 M04-F06 근거 교정 |
| [claim-audit.json](claim-audit.json) | 384개 Claim의 명시적 다축 판정과 검토 완료 상태 |
| [fact-audit.json](fact-audit.json) | 42개 필수 사실의 기존 판정, 유효 Claim과 교정 판정 |
| [score.json](score.json) | 원본·gold 교정·Claim 경계 감사 점수의 분리 집계 |
| [cross-check.json](cross-check.json) | 판정 전환, 새 근거 실패, 원자성 정정과 반복 오류 |
| [snapshots/](snapshots/) | 로컬 감사 검증 코드와 최소 테스트의 읽기 전용 사본 |
| [PROVENANCE.json](PROVENANCE.json) | 공개 파일의 SHA-256 |

## 공개 범위와 한계

기사 전문, 모델 원응답, 생성 Claim 문장, 키, Workspace 주소와 개인 설정은 공개하지 않았다. Claim 번호·modality·선택한 원문 ID·판정·사유만 공개하므로 집계와 판정 규칙은 검토할 수 있지만 의미 정답을 독립적으로 재채점할 수는 없다.

이번 점수 변화는 같은 모델 출력에 평가 경계를 다시 적용한 결과다. 모델의 개선이나 회귀, 최소 schema 자체의 실패 원인, 자동 저장 가능성과 운영 품질을 뜻하지 않는다. 모델 호출과 API 비용은 0이며 제품 코드·DB·migration·metadata·fixture·정식 문서·의존성은 변경하지 않았다.
