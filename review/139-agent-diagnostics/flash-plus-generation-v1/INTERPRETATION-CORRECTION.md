# Flash·Plus 생성 비교의 제품 해석 정정

2026-09-10, Ontology Map Role Harness Reset 세션에서 사용자가 확정한 역할 계약에 따라 해석을 정정한다. 이 문서는 `c438dfce8aaa1e58f499d242a4281997c4a5710a`의 비교 결과를 다시 채점하거나 당시 시험 목적·기준을 소급 변경하지 않는다. 기존 기록에 있는 생성 모델 선택과 후속 진행에 관한 제품 결론만 대체한다.

## 정정 대상과 증거 보존

정정 대상은 [#139 결과 댓글 5610904861](https://github.com/studylida/ontology-map/issues/139#issuecomment-5610904861), [#127 인계 댓글 5610905037](https://github.com/studylida/ontology-map/issues/127#issuecomment-5610905037), [PR #189](https://github.com/studylida/ontology-map/pull/189)의 제품 해석과 이 패킷의 [README](README.md), [보고서](REPORT.md), [기존 검토 요청](REVIEW_PROMPT.md)에 담긴 같은 해석이다. 이전 문서와 댓글은 당시 기록으로 보존하며, 현재 역할과 후속 진행의 해석에는 이 정정을 적용한다.

[manifest.json](manifest.json), [score.json](score.json), [blind-review.json](blind-review.json), [blind-map.json](blind-map.json), [gold.json](gold.json), 호출 메타데이터와 코드 snapshot을 수정하지 않는다. 특히 `score.json`의 `NO_MODEL_CANDIDATE_MEETS_FROZEN_CRITERIA`는 당시 동결 기준으로 계산한 결과로 남긴다. 이 값을 제품의 역할별 모델 배정을 취소하는 결정으로 사용하지 않는다.

[PROVENANCE.json](PROVENANCE.json)의 기존 19개 파일은 원래 hash를 유지한다. 이 정정 문서는 그 뒤에 추가된 해석이며 당시 동결 패킷의 일부였다고 주장하지 않는다.

## 보존하는 관측값

공식 한국어 기사 4건 × 모델 2개 × 반복 2회, 총 16회이며 독립 원문·사건군은 4개다. 모델별 필수 사실 48행은 24개 사실을 두 번 평가한 결과다.

| 항목 | Flash | Plus |
| --- | ---: | ---: |
| 호출 계약 성공 | 8/8 | 8/8 |
| 필수 사실 PASS | 32/48 (66.67%) | 18/48 (37.50%) |
| Claim 근거 실패 | 39/328 (11.89%) | 5/173 (2.89%) |
| 네 축 통과 유효 비중복 Claim | 217/328 | 76/173 |

16/16 호출이 계약을 통과했다. Flash에서 행동 주체를 잘못 바꾼 동일 중대 오류가 두 반복에서 재현됐다. 사전 예약은 `$0.144587`, 실제 추정 비용은 `$0.03756943 / $0.30`이다. 이 금액은 완료된 비교의 기록이며 남은 예산을 새 시험에 이월하지 않는다.

## 현재 허용되는 해석

- 이번 Flash·Plus 생성 비교는 같은 생성 작업의 모델 역량 차이가 현재 실패를 설명하는지 확인한 진단적 model ablation으로만 취급한다.
- Plus를 생성 역할에 넣는 단순 모델 업그레이드는 해결책으로 확인되지 않았다.
- 현재 Flash 생성 하네스에는 필수 사실 보존, Claim별 근거 연결과 행동 주체 보존 문제가 남아 있다.
- 이 비교는 Flash가 생성한 후보를 Plus가 판정하는 실제 역할 조합을 시험하지 않았다. Plus 생성 결과의 근거 실패율은 Plus 판정기의 잘못된 후보 통과율이나 올바른 후보 거절률이 아니다.
- 따라서 “생성 모델 승자 없음”을 제품 결정으로 삼거나 “이 결과 때문에 #127로 넘어갈 수 없음”이라고 한 결론을 철회한다. #127의 역할별 하네스 설계·계약 검토를 진행할 수 있다. 제품 출력 계약·worker·자동 저장 구현이 이미 승인되거나 완료됐다는 뜻은 아니다.
- 원문 구조와 제품 범위 제한이 오류를 줄인다는 인과 효과는 아직 확인하지 않았다. LangChain 도입 자체를 품질 개선 근거로 삼지 않는다.

## 유지하는 역할 배정

provider는 Alibaba Cloud Model Studio 싱가포르다. 사용자는 다음 배정을 변경하지 않았다.

| 역할 | 고정 모델 또는 책임 |
| --- | --- |
| 본문 추출 | `qwen3.7-flash-2026-07-15` |
| 지식 문장·후보 생성 | `qwen3.7-flash-2026-07-15` |
| 근거·modality·귀속, 동일 대상, 의미 중복과 필요한 의미 연결 판정 | `qwen3.7-plus-2026-05-26` |
| 그 밖의 모델 역할 | Flash |
| 조회·실행 순서·결정적 검증·의존 후보 제외·정합화·transaction·DB 저장 | 일반 애플리케이션 코드 |

같은 Plus snapshot을 쓰더라도 판정 목적별 prompt와 Structured Output 계약은 분리한다. 판정기는 제공된 후보와 허용 근거 안에서만 판정하며 새 근거 검색·자동 보충·Claim 수정·자유로운 DB 조회·쓰기·통과할 때까지 재호출을 하지 않는다. reasoning이나 판정 reason을 정답 또는 원인의 증거로 삼지 않는다.

LangChain은 역할별 model·prompt·Structured Output과 일반 함수의 고정 실행 순서에 필요한 최소 기능만 사용한다. LangGraph, memory, 자유로운 tool loop와 범용 Agent framework는 도입하지 않는다. 출력 계약 오류를 수정하기 위한 추가 모델 호출도 만들지 않는다.

## 다음 검증과 제품 경계

다음 단계는 현재 Flash 기준선과 개선된 Flash 하네스를 동일한 Plus 판정·일반 코드 검증 경로에서 비교하는 것이다. 먼저 현재 HTML 정규화에서 실제로 보존·복원할 수 있는 section·문단·목록·표 구조를 모델 호출 없이 확인한다. 재현할 수 없는 구조를 추측하지 않고, 생성 조건의 여러 축을 동시에 바꾸지 않는다. Plus는 각 Claim의 자기 근거만 보며 형제 Claim이나 전체 원문에서 부족한 근거를 보충하지 않는다.

생성 단계와 판정 후의 필수 지식 보존율, 잘못된 후보 통과율, 올바른 후보 거절률, Claim별 근거 충분성, 중대 오류, 유효 비중복 산출량, 제외·UNRESOLVED·의존 후보 수와 호출·token·비용·시간을 구분해 측정한다. 모두 거절해 정확도만 높이는 구성을 성공으로 계산하지 않는다.

이번 네 기사는 개발·회귀 자료로만 사용한다. 후보를 동결한 뒤 원문·사건·번역·재게시 계열이 겹치지 않는 별도 자료로 평가하며, 평가 기준과 중대 오류율의 분모를 실행 전에 고정한다. 새 유료 시험은 호출 수·모델·최악 비용 예약·중단 조건을 제시하고 별도 사용자 승인을 받는다.

별도 자료의 필수 지식 보존율 70% 이상·사전에 정의한 중대 오류율 1% 미만, 후보별 코드 검증과 Plus 판정 통과라는 데모 관문은 유지한다. 반복 중대 오류가 있는 사실군과 그 의존 후보는 자동 승격에서 제외하고 독립적으로 유효한 지식은 유지한다. 이 관문은 아직 평가되지 않았으며 운영 품질 보증이 아니다. 관문 전에는 URL·파일 입력 데모의 Issue·migration·API·UI·SSE 구현을 시작하지 않는다.

기존 `output_schema_definition`, `model_task`, `agent_attempt`, `source_document`, `observation`, `claim_observation`, Node·Claim·Relation·attribute·event와 promotion·publication 구조를 우선 재사용한다. 여러 모델 호출을 같은 모델의 retry로 기록하지 않도록 기존 실행 계약 매핑은 #124·#127에서 확인한다. runtime 후보·판정·의존 정보와 provider 원응답·reasoning·gold는 제품 지식 DB에 저장하지 않는다.

#122·#123의 삭제된 제안을 복원하거나 새 table·column·task kind·publication pointer의 필요성을 미리 가정하지 않는다. 이번 변경은 검토 자료의 해석 정정뿐이며 제품 구현은 승인 후 최신 `origin/main`에서 별도 branch·worktree로 진행한다. PR #189는 Draft로 유지하고 #139·#127은 닫지 않는다.
