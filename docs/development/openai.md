# OpenAI 역할별 실행

## 상태와 범위

Issue #240의 전환 브랜치 구현이다. 코드/MockTransport 검증, 실제 OpenAI 요청 수락, 모델의 의미 정확성, 실제 DB·publication·화면 성공은 서로 다른 검증이다. Luna 중심·Terra 핵심 단계 배치는 초기 권고안이며 실제 품질이 검증되지 않았다. 이 문서는 유료 실행 승인이 아니다.

`llm_config.py`의 한곳에서 모델·effort·출력 옵션을 선택한다. 기존 Kimi/ModelStudio 이름 일부는 import 호환용이며 외부 호출은 OpenAI 하나뿐이다. 자동 router, Luna→Terra 승격, 다른 provider fallback, SDK 자동 재시도, UI 실시간 모델 호출을 추가하지 않는다.

| 역할 | API 모델 | reasoning_effort |
| --- | --- | --- |
| body | gpt-5.6-luna | low |
| claim_support | gpt-5.6-luna | low |
| NODE_CONTEXT | gpt-5.6-luna | low |
| FOLLOWUP_QUESTIONS | gpt-5.6-luna | low |
| KNOWLEDGE_EXTRACTION generation | gpt-5.6-terra | medium |
| meaning_support | gpt-5.6-terra | medium |
| entity_resolution | gpt-5.6-terra | medium |
| claim_duplicate | gpt-5.6-terra | medium |
| NODE_INSIGHT | gpt-5.6-terra | medium |

## API와 출력 계약

단일 endpoint는 `POST https://api.openai.com/v1/chat/completions`다. 현재 단발 Chat Completions 실행기와 응답/usage 계약을 유지하는 최소 변경을 선택했다. Responses API, conversation loop와 이중 endpoint 지원은 구현하지 않는다. 직접 HTTPX 전송에 `retries=0`, `follow_redirects=False`, `trust_env=False`를 적용한다. `stream=false`, `store=false`, 역할별 `reasoning_effort`, `max_completion_tokens`, `response_format.type=json_schema`와 `strict=true`를 보낸다. Kimi `thinking`, `max_tokens`, 임의 sampling 옵션은 보내지 않는다.

`openai_schema.wire_schema()`는 원본 Pydantic schema를 복사해 별도 전송 schema를 만든다. 모든 object를 닫고 모든 property를 required로 만들되 nullable은 원래 허용한 필드에만 유지한다. `const`는 같은 값의 singleton enum으로 표현하고 `default` 주석만 제거한다. `pattern`, 지원되는 `format`, 숫자/배열 제약, `$defs/$ref/anyOf`를 유지한다. 다만 실제 OpenAI D1 요청에서 거절된 Pydantic Decimal의 lookahead 정규식만 동등한 정규식으로 바꾼다. 원본 schema와 Decimal 검증은 그대로다. 알 수 없는 의미 키워드는 예약 전에 거절한다. 이는 임의 JSON Schema를 모두 지원하는 변환기가 아니다. 실제 9개 DTO의 Mock 변환 성공을 실제 API 수락으로 취급하지 않는다.

원본 schema는 prompt에도 그대로 첨부하고 원본 DTO strict parser를 유지한다. Mention TOPIC/topic_name 교차 조건은 wire 설명으로 유도하지만 Python validator를 제거하지 않는다. 날짜·UTC·precision·modality·stance·관계 방향·Claim/Meaning·Entity Resolution·원문 ID/version/quote/offset/hash 검증은 유지한다. DTO를 provider 출력에 맞춰 완화하지 않는다. refusal, 비정상 finish_reason(잘림/content_filter 등), JSON/제품 schema 오류는 정상 empty가 아니다.
실제 D1 생성에서는 binding의 언급 참조에 원문 text가 들어가 모든 의미 연결이 제외됐다. 생성 지시문은 같은 Claim의 `mentions[].mention_id`를 정확히 쓰도록 명시하며, 출력의 잘못된 참조를 자동 보정하지 않는다.

Issue #242의 내부 D1–D3 데모에서는 공동 사실을 불필요하게 분해하지 않는 기존 규칙을 유지하면서, 서로 독립적으로 중요한 사실을 하나의 headline Claim으로 압축하지 않고 원자 Claim으로 제안하도록 generation 지시문을 보완한다. FOLLOWUP_QUESTIONS와 NODE_INSIGHT는 이미 여러 Claim의 종합·근거 한계·사실과 해석의 구분을 요구하므로 prompt와 identity를 바꾸지 않는다.

NODE_CONTEXT의 `node-context-244-v2`는 일반적인 인물·회사 소개가 아니라 등록된 공개 자료 전체에서 대상이 어떤 활동·관계·발언으로 나타나는지 1–3문장으로 요약한다. 제한된 자료를 주요 사업·전문 분야·지속적인 관심사나 전체 입장으로 일반화하지 않으며, 자료 범위가 좁으면 그 한계를 문장에 드러낸다. 입력과 출력 DTO는 유지하지만 prompt version이 task identity에 포함되므로 이전 version의 READY 결과는 현재 요약으로 간주하지 않는다. 읽기 API는 version 일치 여부를 반환하고 web은 정상 publication으로 새 결과가 준비될 때까지 이전 설명을 숨긴다. 이 변경은 provider 호출이나 기존 결과의 자동 재생성을 수행하지 않는다.

응답 model은 실제 요청 model과 정확하게 일치해야 한다. 공식 문서로 확인하지 않은 dated snapshot 접두사를 임의 허용하지 않는다. 실제 API가 다른 snapshot을 반환하면 해당 계약을 별도 확인하기 전에는 fail-closed로 중단한다.

## identity와 과거 task

새 effective input에는 실제 provider, endpoint, 전체 또는 해당 역할 profile, effort, 출력 옵션, wire schema/profile 버전, 원본 출력 지시문 hash, 요청 한도와 기존 prompt/schema/실행 설정이 들어간다. helper 역할 설정도 KE identity에 포함한다. 캐시와 결과 identity 역시 이 설정을 포함하므로 예전 Kimi 결과를 새 모델 결과로 재사용하지 않는다.

Kimi task 14를 GPT로 native retry하지 않는다. 실제 전환은 별도 승인을 받은 새 effective input과 명시적인 새 `execution_generation`의 별도 task로 수행한다. 기존 RUNNING/RESERVED/UNKNOWN/attempt/lease, 미확정 비용 상한과 archive는 초기화·수정하지 않는다. 이 코드 변경만으로 DB migration/activation이나 task 생성이 필요하다는 뜻은 아니다.

## 한도와 예산

앱의 기존 입력 상한 223,232, 출력 상한 32,768, 입력 예약 상한 262,144 token을 자동 확대하지 않는다. 실제 publication 출력 한도도 NODE_CONTEXT 2,048, FOLLOWUP_QUESTIONS 2,048, NODE_INSIGHT 8,192로 유지한다. `max_completion_tokens`는 reasoning을 포함한다. 응답의 `completion_tokens`에 reasoning을 다시 더하지 않는다.

2026-09-18 공식 일반 처리·짧은 context 기준 USD/백만 token은 Luna 입력 0.20/캐시 입력 0.02/출력 1.20, Terra 입력 2.00/캐시 입력 0.20/출력 12.00이다. cache write는 일반 입력의 1.25배로 안내돼 있다. `token_cost`는 할인 없이 모든 입력을 cache-write 가격으로 계산한 `charged_upper_usd`이며 실제 청구액 추정치로 표시하지 않는다. 선택적 cached/cache_write/reasoning 사용량은 상호 범위를 검사하고 비공개 envelope에 남긴다. 역사적 `kimi-k2.6` 비용 함수는 당시 0.95/4.00을 유지한다.

새 모델의 큰 context가 기존 예약액보다 큰 입력을 수락하지 않도록 원문·prompt·두 schema를 포함한 전체 직렬화 요청에도 64,512 byte 상한을 적용한다. `(262144 - 4096) // 4`라는 보수적인 byte 기반 admission 정책으로, 정확한 tokenizer 계산이나 공급자의 과금 보증은 아니다. 각 caller의 byte 상한이 더 작으면 그 값을 적용한다. 이 정책은 큰 입력을 더 일찍 거절할 수 있으며 입력 예약액이나 실제 승인 예산을 조용히 늘리는 대신 선택한 제한이다. 장문 할증 영역의 요청을 허용하려면 별도 tokenizer/admission/예산 검토가 필요하다. 실제 usage가 한도를 넘거나 미확정이면 원장을 확정 성공으로 메우지 않고 중단한다.

generation read timeout 180초, 다른 역할과 connect/write/pool timeout 60초를 유지한다. 기존 10분 lease나 승인 call/cost cap은 늘리지 않는다.

## pacing·lease·transaction

실제 전송에는 `ProcessPacer`의 명시적인 양수 간격과 활성 `PilotBudget`이 모두 필요하다. 공식 모델 Tier 표를 사용자 계정 RPM/TPM으로 가정하거나 기본 간격을 임의 입력하지 않는다. 모든 역할은 같은 프로세스 turn을 공유한다. turn은 실제 전송 시작 시각을 기준으로 간격을 지키며 예약 전 대기, 대기 후 lease 확인, 전송 직전 lease 재확인을 수행한다. 실제 전송은 한 번이며 긴 generation 다음 helper 연속 호출에도 동일한 간격을 적용한다.

대기와 모델 I/O는 DB transaction 밖에 둔다. ER/Claim duplicate는 먼저 기존 REPEATABLE READ의 읽기 snapshot을 준비하고 transaction을 닫은 뒤 모델을 부른다. canonical write 시점의 기존 재검증은 유지한다. durable generation은 기존 slot 소유자만 예약/기록하며 helper는 durable generation attempt가 되지 않는다. 한 프로세스 제한은 다른 프로세스·앱·동일 계정 전체의 제한기가 아니다.

Retry-After와 허용한 rate-limit/remaining/reset 헤더만 안전하게 보관한다. 알려진 quota/billing 429는 임시 rate-limit과 구별하며 자동 retry하지 않는다. 429·timeout에서 사용량이 미확정이면 기존 pilot 중단과 미확정 예약을 유지한다. 중단된 pilot을 자동으로 풀거나 예약을 0 token SUCCESS로 바꾸지 않는다.

## 키와 공통 연결

`ontology_map.openai_clients.openai_clients`는 명시적 `SecretStr` 또는 로컬 `OPENAI_API_KEY`만 읽는다. `MOONSHOT_API_KEY`, Qwen key, Codex/Orca/ChatGPT 구독 토큰은 사용하지 않는다. key 존재 자체는 실행 승인이 아니다. `server/.env.openai.example`은 항목 설명용이며 자동으로 읽거나 유료 실행하지 않는다.

호출자는 승인된 값으로 `ProcessPacer(min_interval_seconds)`를 만들고 `openai_clients(helper_budget, pacer=pacer)` 안에서 기존 `application_execution.run_document(..., pilot=pilot)` 경계를 사용한다. client 생성만으로 전송/DB 접근/원장 생성은 하지 않는다. 실행 대상·예산·총 횟수·원문 공개 범위·새 execution_generation이 승인되기 전에는 이 연결을 실행하지 않는다.

## 응답 보관과 안전한 진단

보관 모듈의 기존 이름 `kimi_response_archive.py`는 최소 변경을 위해 유지한다. OpenAI 응답 기본 경로는 pilot 원장 옆 `openai-responses`, pilot 없는 Mock 호출은 `~/.local/state/ontology-map/openai-responses`다. `ONTOLOGY_MAP_OPENAI_RESPONSE_DIR`로 Git 밖 절대 경로를 명시할 수 있다. 이전 Kimi 경로와 환경값은 새 호출에 재사용하지 않으며 기존 파일은 건드리지 않는다.

성공/HTTP 오류의 전체 `response.content` bytes를 HTTP 상태/JSON/제품 parser보다 먼저 비공개 파일에 저장한다. 이는 HTTPX 압축 해제 후 파서가 받는 전체 본문이며 압축 전 네트워크 packet은 아니다. 디렉터리 0700/파일 0600, no-follow/exclusive 생성, 원본 덮어쓰기 금지를 유지한다. request·response hash, 로컬 response_id, provider/model, 역할, task/slot/pilot sequence, 안전한 envelope 식별자/usage와 실패 단계/field path를 연결한다. key·인증 헤더·source·raw response는 콘솔/PR/공유 artifact/제품 DB에 저장하지 않는다.

보관 I/O 실패는 제품 판정을 바꾸지 않는다. 무응답 timeout은 NO_RESPONSE이며 공급자 미수신/미과금이라는 뜻이 아니다. 오류 원문이나 임의 header/model 문자열을 진단으로 내보내지 않는다.

## 검증과 실제 D1 승인 관문

MockTransport/가짜 시계는 요청·파싱·진단·보관·단발 전송·예산·pacing/lease 경계만 검사한다. 실제 형식 수락과 의미 품질은 별도다. 실제 D1 한 건은 유효 Claim/Evidence 1개 이상, 정확한 원문 식별/인용 연결, 공식 canonical 저장·promotion COMMITTED·publication READY, 실제 API와 화면의 동일 근거까지 모두 확인해야 한다. HTTP 200/attempt SUCCESS/정상 empty만으로 대신하지 않는다.

실행 전 운영자는 두 모델의 API 권한, 실제 계정/프로젝트 RPM·TPM과 다른 호출 영향, 승인 call/USD cap, 별도 private 원장/응답 경로, 새 execution_generation, 대상 문서와 원문 공개 범위를 확인한다. Orca의 로컬 작업 설정은 xhigh이며 제품 API reasoning_effort와 별개다. 승인된 작은 표본의 사람 근거 기반 Luna/Terra 비교는 후속 평가이며 이 문서로 추가 유료 호출을 허가하지 않는다.

## 공식 확인 출처

- [Luna 모델](https://developers.openai.com/api/docs/models/gpt-5.6-luna), [Terra 모델](https://developers.openai.com/api/docs/models/gpt-5.6-terra), [가격](https://developers.openai.com/api/docs/pricing)
- [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)
- [Reasoning](https://developers.openai.com/api/docs/guides/reasoning), [Rate limits](https://developers.openai.com/api/docs/guides/rate-limits)
