# Kimi 국제판 LLM 실행

## 적용 범위와 상태

[Issue #233](https://github.com/studylida/ontology-map/issues/233)의 사용자 승인에 따라 모든 LLM 호출을 Kimi 국제판으로 전환한다. 임시 데모 모드나 provider fallback이 아니다. 이 문서는 해당 구현 브랜치의 실행 계약을 설명하며, 실제 계정 호출과 D1의 DB → READY → 화면 성공은 별도로 검증해야 한다.

| 역할 | 실행 경계 |
| --- | --- |
| 본문 선택·지식 생성 평가·Claim/Meaning 판정 | `KimiModels.call` |
| Entity Resolution·Claim 중복 판정 | 기존 공식 proposer → `KimiModels.call` |
| durable KNOWLEDGE_EXTRACTION | `KimiGenerationAdapter.prepare` |
| NODE_CONTEXT·FOLLOWUP_QUESTIONS·NODE_INSIGHT | 기존 제품 adapter → `KimiStructuredTransport` |

기존 `ModelStudio*`, `FLASH`, `PLUS` import는 외부 호출부 호환을 위해 남지만 모두 같은 Kimi 구현으로 연결된다. Alibaba endpoint와 다른 모델은 preflight에서 거절한다. 옛 #139 유료 시험 CLI는 폐기했으며, 과거 Qwen 시험의 예산·승인·credentials를 새 Kimi 실행으로 이어받지 않는다.

## 요청과 검증

공식 국제판 endpoint는 `https://api.moonshot.ai/v1`이고 기본 모델은 `kimi-k2.6`이다. `thinking={"type":"disabled"}`, `stream=false`, `response_format={"type":"json_object"}`를 사용한다. Kimi의 고정 sampling 제약 때문에 temperature와 top_p 등을 보내지 않는다. 설정은 `llm_config.py` 한 곳이 소유한다.

제품 JSON Schema는 변경 없이 system message 뒤에 결정적으로 첨부한다. `pattern`, `format`, `$ref`는 provider grammar로 제출하지 않으며, 응답의 필수 필드·타입·Mention·시간 및 각 제품 의미 검증은 기존 코드로 수행한다. JSON mode는 유효한 제품 출력을 보장하지 않는다. 원문·source ID·인용 범위·hash, Claim/Meaning 판정, Entity Resolution, canonical promotion 및 publication READY 조건은 완화하지 않는다. 자동 보정이나 출력 재요청 루프는 없다.

모든 helper와 durable adapter는 공통 단발 HTTP transport를 사용한다. 요청 byte 상한을 전송 전에 검사하고, redirect·자동 retry·환경 proxy를 사용하지 않는다. 실제 모델과 usage가 확인되지 않은 호출은 보수적인 예약액을 유지하고 pilot을 중단한다. usage가 확인된 잘린 출력은 사용량을 계산하되 제품 출력 실패로 남긴다. 원시 응답·reasoning·키·원문은 ledger에 쓰지 않는다.

## 한도와 실행 식별

K2.6의 공식 context는 256K다. 애플리케이션은 보수적으로 입력 223,232 + 출력 32,768 = 256,000 token을 상한으로 사용한다. 기존 1,000,000 입력 상한을 지정한 로컬 caller는 새 상한 이하로 명시적으로 변경하고 runtime identity를 다시 구성해야 한다. model window와 실제 tokenizer의 경계 판단은 provider가 담당하며 로컬에서 정확한 token 수를 추측하지 않는다.

유료 전송 상한은 caller의 명시적 `PilotBudget`이 소유한다. helper의 `Budget`만으로는 실제 전송이 허용되지 않는다. 단가는 2026-09-18 공식 국제판의 uncached 입력 $0.95 / 출력 $4.00 (백만 token 기준)를 사용한다. cache 할인·충전액·프로모션은 가정하지 않는다. 불확실한 입력 사용량은 262,144 token으로 보수적으로 예약한다. 가격이나 모델 변경 시 설정·한도·테스트를 함께 갱신한다.

`llm_config.request_identity_settings()`의 provider·endpoint·model·wire option·출력 지시문 hash·profile 버전은 실제 요청 구성과 공유된다. KE effective input에는 이 설정을 직접 포함하고, NODE_CONTEXT/FOLLOWUP/INSIGHT는 기존 `*_execution.py`의 structured request identity를 통해 포함한다. 제품 모델 식별자도 실제 Kimi 모델로 바꾼다. 제품 output schema는 그대로이므로 이 변경만을 위한 schema migration이나 활성 schema 덮어쓰기는 필요하지 않다.

기존 FINAL_FAILED task의 상태·attempt·slot·lease를 초기화하지 않는다. 수동 재처리는 새 `execution_generation`을 명시하고, 기존 `runtime.identity_settings()`와 실제 입력을 다시 일치시킨다. 과거 Qwen 기록과 결과는 수정하지 않으며, Kimi 품질 검증의 증거로 재사용하지 않는다.

## 기존 애플리케이션 경로 연결

실제 키는 채팅·Issue·PR·소스에 넣지 않는다. 별도 개인 환경에 `MOONSHOT_API_KEY`를 설정한다. `server/.env.kimi.example`은 변수 이름만 제공한다. 이 파일을 import할 때 자동으로 읽거나 다른 provider 키를 대체 사용하지 않는다.

아래는 기존 caller에서 이미 검증된 `engine`, `document_id`, `runtime`, `execution`, 각 예산·판정 한도를 전달하는 연결 예시다. 새 CLI나 새 실행기를 만들지 않는다. `execution_generation`은 예를 들어 `d1-kimi-v1-01`처럼 재처리를 구분하는 값으로 지정한다.

```python
from ontology_map.application_execution import run_document
from ontology_map.kimi_clients import kimi_clients

# helper_budget, pilot: 이 실행에 명시적으로 허용한 상한.
# runtime / execution: 기존 source, ontology, validator와 실제 한도를 반영.
with kimi_clients(helper_budget) as clients:
    result = run_document(
        engine=engine,
        document_id=document_id,
        worker_name=worker_name,
        execution=execution,
        runtime=runtime,
        helpers=clients.helpers,
        prepare_generation=clients.generation.prepare,
        propose_resolution=clients.resolution_proposer(resolution_limits),
        propose_claim_duplicate=clients.claim_duplicate_proposer(duplicate_limits),
        prepare_node_context_provider=clients.node_context.prepare,
        prepare_followup_provider=clients.followup.prepare,
        prepare_insight_provider=clients.insight.prepare,
        pilot=pilot,
    )
```

`run_document`는 공식 enqueue → extraction → finalizer → post-commit publication 순서를 유지한다. COMMITTED batch의 publication만 미완료이면 기존 `resume_publication`을 사용한다. 초기화나 새 extraction으로 후속 실패를 숨기지 않는다. terminal 후속 task는 단순 재호출만으로 초기화되지 않는다.

## 완료 확인

HTTP 200 또는 JSON 파싱 성공만으로 완료라고 하지 않는다. 실제 D1에서는 유효한 후보가 하나 이상 남고, Claim·Evidence가 D1의 정확한 source·quote·offset·hash에 연결되어 저장되며, 공식 promotion COMMITTED와 publication READY를 거친 뒤 실제 API 및 화면에서 같은 근거가 표시되는지 확인한다. mocked HTTP 회귀, 실제 유료 provider 실행, 제품 DB와 화면 성공, formal 모델 품질 관문은 서로 다른 증거다.

기존 제품 검증이 빈 질문이나 빈 Insight를 정상 결과로 인정하는 경우 그 의미는 유지한다. 모델 교체를 이유로 가짜 질문·보고서를 채우거나 READY 조건을 생략하지 않는다. 읽기 API와 화면 조작은 LLM 호출을 시작하지 않는다.

## 공식 문서

- [모델별 파라미터](https://platform.kimi.ai/docs/api/models-overview)
- [Kimi K2.6 안내](https://platform.kimi.ai/docs/guide/kimi-k2-6-quickstart)
- [JSON mode](https://platform.kimi.ai/docs/guide/use-json-mode-feature-of-kimi-api)
- [Chat Completions](https://platform.kimi.ai/docs/api/chat)
- [국제판 모델 가격](https://platform.kimi.ai/)
