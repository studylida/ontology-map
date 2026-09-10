# ontology-map 기사 전체 최소 추출 진단

이 패킷은 [#139](https://github.com/studylida/ontology-map/issues/139)에서 원문 보존형 prompt를 유지한 채 기사 전체를 추출할 때, 풍부한 진단 출력과 최소 runtime 출력의 실행 가능성을 확인한 개발 시험 자료다. 3,000-token 비교가 길이 오류로 성립하지 않아, 별도 동결 라운드에서 최소 출력만 6,000 tokens로 확인했다.

| 기준 | 값 |
| --- | --- |
| 시험 코드가 있던 로컬 HEAD | `ca8c8b62ca993c74c2ff48dde13c488bce1c87b4` |
| 시험 종료 시 확인한 `origin/main` | `31150578d51033653c68aba3faaf8a853716c1dc` |
| 3,000-token 동결 manifest | `375b3230088dc83460282a488cc6340a6cfce45a6ae2d2ce97476dc982f393d8` |
| 6,000-token 동결 manifest | `9b967c78fe5292a13a4b2310ebb9623b34ed9136efb78a7de425cd5a2a5dcdde` |

## 결론

- 3,000-token 라운드는 16회 중 12회가 정확히 출력 상한에서 끝나 의미 비교를 하지 않았다. 풍부한 출력은 8/8, 긴 기사 M01·M02의 최소 출력은 4/4가 잘렸다.
- 6,000-token 최소 출력은 8/8 계약을 통과했지만, 필수 사실 엄격 PASS는 20/42이고 전체 384개 Claim 중 74개가 연결된 `source_ids`만으로는 지원되지 않았다.
- 되풀이된 귀속·modality·선행 근거 오류가 여섯 사실에서 남아 사전 품질 기준에 따라 후보를 기각했다.
- prompt가 제외하라고 한 일반 정의 20개와 제목·본문 중복도 별도 selection 결함으로 확인했다. 이 항목은 출력을 본 뒤 발견했으므로 사전 점수에 소급해서 섞지 않았다.
- 이 결과는 제품 출력 계약, worker, 자동 저장 또는 운영 품질을 승인하지 않는다. 새 영속 schema도 요구하지 않는다.

## 파일 안내

| 파일 | 내용 |
| --- | --- |
| [REPORT.md](REPORT.md) | 설계, 결과, 해석, 한계와 다음 판단 |
| [REVIEW_PROMPT.md](REVIEW_PROMPT.md) | WEB GPT 6 Pro 독립 검토 요청 |
| [plan-3k.md](plan-3k.md) | 최초 풍부한 출력 대 최소 출력 비교 계획 |
| [plan-6k.md](plan-6k.md) | 길이 오류 뒤 최소 출력만 다시 확인한 계획 |
| [manifest-3k.json](manifest-3k.json), [manifest-6k.json](manifest-6k.json) | 출력 확인 전 동결한 설정·기준·요청 해시 |
| [gold.json](gold.json) | 출력 전에 동결한 필수 사실 21개와 근거 기준 |
| [review.json](review.json) | 6,000-token 결과의 단일 Codex 수동 판정 원장 |
| [score.json](score.json) | 동결 기준으로 산출한 점수와 후보 결정 |
| [call-metadata-3k.json](call-metadata-3k.json), [call-metadata-6k.json](call-metadata-6k.json) | 원문과 모델 출력 없이 남긴 호출·비용·종료 메타데이터 |
| [source-index.json](source-index.json) | 공식 원문 URL, 해시, 길이와 단위 수 |
| [input-contract.json](input-contract.json) | 비교 prompt와 strict JSON Schema |
| [snapshots/](snapshots/) | 로컬 시험 코드·판정 작성 코드·최소 테스트의 읽기 전용 사본 |
| [PROVENANCE.json](PROVENANCE.json) | 공개 파일의 SHA-256 |

## 공개 범위와 한계

공식 기사 전문, 모델 원응답, 전체 생성 문장, API 호스트·키·개인 설정은 게시하지 않았다. `review.json`에는 필수 사실 ID와 생성 Claim 번호별 판정·사유만 있다. 따라서 패킷만으로 집계와 판정 정책은 감사할 수 있지만, 원문과 생성문을 직접 대조해 의미를 독립 재채점할 수는 없다.

이번 6,000-token 라운드는 3,000-token 길이 실패를 본 뒤 출력 상한을 고른 개발 자료다. 같은 네 기사를 새 독립 자료로 다시 세지 않는다. 판정자는 `Codex manual semantic review against pre-frozen gold` 한 명이며 사람 독립 평가나 운영 검증으로 설명하지 않는다.
