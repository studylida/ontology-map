# ontology-map Agent 진단 시험 검토 자료

이 자료는 [#139](https://github.com/studylida/ontology-map/issues/139)의 한국어 지식 추출·검증 시험을 WEB GPT에서 독립적으로 검토하기 위한 것이다. 결과 댓글은 이미 GitHub에 있었지만 시험용 prompt와 코드 대부분은 로컬의 Git 제외 폴더에만 있었다. 이 branch에는 공개 검토에 필요한 부분만 모았다. 제품 구현이나 정식 계약으로 병합하기 위한 변경이 아니다.

## 후속 비교 자료

[원문 보존형 추출 비교](original-preserving-v1/README.md)는 이 자료에 대한 첫 독립 검토의 추천을 받아, 기존 R7 조건과 원문 보존 문구 하나만 추가한 조건을 새 공식 한국어 기사 8건에서 비교한 후속 시험이다. 집계와 비식별 평가 원장은 공개하지만 기사 전문과 모델 원응답은 공개하지 않는다. 후속 검토는 [전용 검토 요청](original-preserving-v1/REVIEW_PROMPT.md)을 기준으로 한다.

[인접 원문 ID 비교](adjacent-context-v1/README.md)는 원문 보존 문구를 유지한 채 위치상 인접한 원문 ID 표시만 바꾼 두 번째 후속 시험이다. 인접 ID 후보는 근거 연결을 반복적으로 개선하지 못해 기각했으며, 별도로 확인한 싱가포르 strict JSON Schema 호환성 결과도 같은 패킷에 분리해 기록했다.

[기사 전체 최소 추출 진단](minimal-extraction-v1/README.md)은 focus 문장을 미리 고르지 않고 기사 전체를 추출한 세 번째 개발 시험이다. 3,000-token 풍부한 출력 비교는 길이 오류로 성립하지 않았고, 6,000-token 최소 출력은 계약을 통과했지만 필수 사실·연결 근거·선택 품질 기준을 충족하지 못해 기각했다.

[개별 Claim 근거 경계 무호출 감사](evidence-boundary-audit-v1/README.md)는 같은 384개 Claim과 42개 필수 사실을 다시 호출하지 않고 교차 감사한 결과다. 기존 점수를 보존하면서 형제 Claim의 근거 합집합으로 개별 Claim의 부족을 메우지 않는 기준과 M04-F06 gold 교정을 분리했다.

## 시작점

검토자는 [검토 질문 전체](REVIEW_PROMPT.md)를 먼저 읽고, [수행 과정과 결과](EXPERIMENTS.md), [재구성 사례](CASES.md), 실제 prompt·계약·코드 순으로 확인한다. 자료를 전달한 메시지에 적힌 commit을 기준으로 판단하고 이후 변경과 섞지 않는다.

| 항목 | 기준 |
| --- | --- |
| 검토 branch | `docs/139-agent-review` |
| 검토 branch의 main 기준 | `ffbca386a875b517137412d385b3eea36719521e` |
| 실제 시험 당시 로컬 HEAD | `ca8c8b62ca993c74c2ff48dde13c488bce1c87b4` |
| 시험 당시 코드 변경 위치 | Git에서 제외된 로컬 시험 폴더. 제품 추적 파일 변경 없음 |
| 이번 게시 범위 | `review/139-agent-diagnostics/`의 공개 검토 자료만 추가 |
| 현재 판단 | 부분 개선과 잔여 실패가 확인됨. #139 완료나 운영 품질 달성 아님 |

검토 branch는 최신 main에서 만들었지만, 시험을 그 main에서 다시 수행한 것은 아니다. 실제 시험 코드의 읽기 전용 사본과 당시 결과를 추가했을 뿐이다. 이번 게시 과정에서는 모델 호출·데이터 적재·제품 코드·DB·migration·metadata·fixture·정식 문서·의존성 변경을 하지 않는다. PR·merge도 하지 않는다.

## 무엇을 확인할 수 있는가

| 자료 | 성격과 확인 가능한 범위 |
| --- | --- |
| [EXPERIMENTS.md](EXPERIMENTS.md) | 로컬 보고서와 Issue 결과를 바탕으로 정리한 과정·집계·중단 상태. 독립 재채점 결과가 아님 |
| [CASES.md](CASES.md) | 오류 구조를 이해하도록 재구성한 예시. 실제 원문·Claim·원응답을 그대로 옮긴 자료가 아니며 새 측정 자료도 아님 |
| [prompts-and-schemas.json](prompts-and-schemas.json) | 실제 시험에 사용한 system prompt 11종과 입력·출력 JSON schema. prompt 안의 schema와 별도 `output_schema`를 함께 보존 |
| [results-metadata.json](results-metadata.json) | 마지막 49회 호출의 설정·시간·비용·해시, 고정 기대값과 판정·근거 ID 비교, 응답의 판정·ID 발췌. 원문·Claim 문장·이유·전체 응답은 제외 |
| [evaluation-summary.json](evaluation-summary.json) | 마지막 시험의 로컬 평가 요약 사본. `github` 항목은 이전 결과 댓글의 확인 기록이며 이번 branch 게시 기록은 아님 |
| [snapshots/diagnostics.py.txt](snapshots/diagnostics.py.txt) | 직전 Preservation·복합 Fidelity 입력·출력·검증·prompt 코드 |
| [snapshots/contracts.py.txt](snapshots/contracts.py.txt) | 마지막 Evidence·Atomicity 입력·출력·검증·prompt 코드 |
| [snapshots/trial_residual.py.txt](snapshots/trial_residual.py.txt) | 마지막 대조 시험의 요청 구성과 실행 경계 코드 |
| [snapshots/amend_residual.py.txt](snapshots/amend_residual.py.txt) | 한 차례 prompt 수정 및 확대 시험 코드 |
| [snapshots/score.py.txt](snapshots/score.py.txt) | 고정 기대값과 판정·근거 ID 일치를 계산하는 코드. 이유의 의미 정확성은 판정하지 않음 |
| [PROVENANCE.json](PROVENANCE.json) | 공개 자료와 보존한 로컬 원본의 SHA-256. 해시가 원본의 의미 정확성이나 공개되지 않은 내용을 증명하는 것은 아님 |

`snapshots/`는 코드 검토용 `.txt` 사본이다. 실행에 필요한 이전 시험 모듈·원자료·전체 gold·transport·credential loader는 포함하지 않는다. 완전한 실행·재현 패키지라고 주장하지 않으며, 그대로 실행하면 안 된다. 실제 요청은 system prompt뿐 아니라 개별 원문·후보·설정으로 구성되므로 prompt 공개만으로 개별 요청을 재현할 수도 없다.

## 공개하지 않은 자료와 검토 한계

기사 전문, 원시 provider 응답 전체, 추론 기록, 키와 개인 설정, 비공개 실행 환경 정보는 싣지 않았다. 로컬 원본은 삭제하거나 덮어쓰지 않았다. 공개 자료로 prompt·책임 경계·집계의 일관성을 검토할 수 있지만 원문과 Claim 및 이유를 다시 읽어 의미 정답을 독립적으로 확정할 수는 없다. 추가 근거가 필요한 주장은 확인 불가로 표시하고, 필요한 자료의 종류를 제시해야 한다. 비공개 자료를 공개하라는 요청으로 바꾸지 않는다.

## 제품 계약과 Issue 연결

현재 병합된 계약은 [문서 안내](../../docs/README.md), [논리 스키마](../../docs/data/logical-schema.md), [물리 스키마](../../docs/data/physical-schema.md), [생성된 schema reference](../../docs/data/schema-reference.md)를 따른다. [ADR-0005](../../docs/architecture/decisions/current/0005-persist-model-task-contracts-not-provider-payloads.md)는 model task 계약과 provider payload를 구분하고, [ADR-0006](../../docs/architecture/decisions/current/0006-separate-promotion-and-publication.md)은 지식 승격과 사용자용 결과 publication을 구분한다.

- [#139](https://github.com/studylida/ontology-map/issues/139): 시험 계획·진행·결과. [마지막 49회 결과 댓글](https://github.com/studylida/ontology-map/issues/139#issuecomment-5581222036).
- [#127](https://github.com/studylida/ontology-map/issues/127): KNOWLEDGE_EXTRACTION 출력 계약과 최소 worker의 후속 결정. [관련 시험 결과 댓글](https://github.com/studylida/ontology-map/issues/127#issuecomment-5581227461).
- [#125](https://github.com/studylida/ontology-map/issues/125): Agent 역할·실행 경계와 추출 후 정합화 책임.
- [#124](https://github.com/studylida/ontology-map/issues/124): frozen schema와 기존 계약 감사.
- [#126](https://github.com/studylida/ontology-map/issues/126): 초기 ontology 검토. [#128](https://github.com/studylida/ontology-map/issues/128): Node 동일 대상 판정 책임.

Issue의 승인된 변경안과 현재 main 구현은 구분한다. 이 자료에서 사용하는 Selection·Composer·Preservation·Fidelity·Evidence·Atomicity는 시험 역할명이다. 모두 별도 제품 Agent나 `model_task.task_kind`로 승인됐다는 뜻이 아니다. 지금의 핵심 검토 질문은 역할을 얼마나 더 만들지가 아니라, 최소한의 생성·코드 검증·의미 판정으로 실제 추출 품질을 높일 수 있는가이다.
