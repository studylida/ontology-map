"""Verification-branch document edits; only resulting docs enter the feature."""
from pathlib import Path
p=Path('.')
q=p/'docs/architecture/README.md'
s=q.read_text()
s=s.replace('현재 제품 구현은 외부 수집 시스템이나 모델 provider와 연결되지 않는다. 별도 모델 시험을 제품 연결로 해석하지 않는다.', '외부 자료 수집 시스템은 연결하지 않는다. #127의 Python worker 함수는 명시적으로 전달한 ModelStudio adapter를 통해 준비된 자료를 처리할 수 있다. HTTP API에서 worker를 자동 실행하지 않으며 실제 유료 provider 실행·의미 품질과 별도 모델 시험을 코드 연결 검증과 구분한다.')
s=s.replace('| Entity Resolution | 후보 조회·판정 함수와 promotion 결합 경계 | 구현, 상위 호출자 연결 필요 |','| Entity Resolution | 후보 조회·판정 함수와 promotion 결합 경계 | #127 worker가 기존 runtime 함수를 직접 호출 |')
s=s.replace('| Agent·worker | 전체 실행 진입점 없음 | 미구현 |','| KNOWLEDGE_EXTRACTION worker | `knowledge_extraction.enqueue` / `run_task` Python 함수 | durable 생성 호출·검증·정합화·promotion 연결. scheduler·publication은 제외 |')
s=s.replace('- 제품 수준 durable Agent·worker 실행 진입점은 아직 없다. [#125](https://github.com/studylida/ontology-map/issues/125)의 실행·retry·reprocess 계약은 승인됐고, 실제 `KNOWLEDGE_EXTRACTION` runner와 #128 runtime helper 연결은 [#127](https://github.com/studylida/ontology-map/issues/127)이 소유한다. 모델 시험의 역할 분리가 제품 프로세스 분리를 뜻하지 않는다.', '- #127은 준비된 자료를 처리하는 동기 Python worker 함수다. 운영 scheduler·배포 프로세스와 publication은 별도로 구현되지 않았다. active 출력 계약·ontology·지원 validator reference data를 조회하며 누락을 자동 seed나 가짜 revision으로 보충하지 않는다. 실제 provider 의미 품질과 Agent→DB→READY 전체 실행을 완료로 보지 않는다.')
marker='## 현재 실행과 배포'
text='''### Durable KNOWLEDGE_EXTRACTION worker

`knowledge_extraction.enqueue`는 불변 문서와 실제 active 출력 계약·ontology·validator를 검증해 결정적 cache key로 제품 작업을 만든다. 같은 task의 SUCCESS는 payload 복원 없이 no-op이며 VALIDATION_BLOCKED/FINAL_FAILED 작업을 초기화하지 않는다. 수동 FINAL_FAILED 재처리는 원래 task와 새 execution generation을 명시한다.

`run_task`는 #125의 10분 lease를 얻은 뒤 기존 `extraction` 본문 선택·생성·근거 판정을 사용한다. 생성 요청의 정확한 HTTP wire를 구성하고 local preflight를 마친 뒤에만 RESERVED slot을 commit한다. ModelStudio의 다른 역할과 #128·Claim 의미 재사용 판정은 runtime 호출이며 durable retry attempt로 섞지 않는다. raw 응답과 runtime 후보는 DB에 저장하지 않는다.

`knowledge_reconciliation`은 #128의 기존 resolver를 직접 호출하고 unresolved 의존 연결을 제외한다. 연결을 뺀 Claim은 남은 의미를 다시 판정한다. DB code·revision·방향·endpoint·값 종류·canonical unit에 맞는 사실만 승격하며 미지원 MAX_MEMORY_BANDWIDTH나 미승인 EVENT→TECHNOLOGY code를 발명하지 않는다. 기존 Claim은 동일 canonical 구조 대상과 자기 근거를 대조해 재사용하고 기존 문장·의미 연결을 재작성하지 않는다.

`db/extraction_promotion`은 #128의 caller-owned context 안에서 Node binding으로 Claim·Relation·attribute·event와 Observation 근거를 저장한다. Relation은 기존 identity key로 재사용하고 검증된 SUPPORT 근거를 요구한다. 이미 채택된 사건 시간과 다른 값은 덮어쓰지 않는다. Claim 자체의 asserted 시간과 사건 시간을 섞지 않는다. 마지막에 batch COMMITTED와 model_task SUCCESS를 같은 transaction에서 확정하며 publication은 NOT_STARTED로 둔다. 정상 zero는 promotion 없이 SUCCESS, 전부 차단은 VALIDATION_BLOCKED로 처리하되 3 slot 소진 후 미적용 종료는 FINAL_FAILED다.

검증은 실제 migration을 적용한 별도 PostgreSQL과 mock HTTP provider를 사용한다. source metadata·ontology의 실제 운영 등록, 유료 provider 결과와 의미 품질은 이 검증이 증명하지 않는다.

'''
assert marker in s
s=s.replace(marker,text+marker)
q.write_text(s)
q=p/'docs/operations/database.md'
s=q.read_text().replace('현재 `db/model_tasks.py`와 `durable_provider.py`는 호출 ledger·단일 전송 경계다. 이 경계의 통과를 전체 extraction·ontology·Claim promotion 또는 publication 구현 완료로 해석하지 않는다. 호출자는 실제 active output contract와 prepared request를 검사하고 product 성공을 같은 promotion transaction에 연결해야 한다.', '''`db/model_tasks.py`와 `durable_provider.py`는 호출 ledger·단일 전송 경계다. 제품 worker는 `knowledge_extraction.py`에서 exact-wire 예약 hook과 기존 ModelStudio adapter를 연결한다. 호출 ledger 검증과 실제 추출·promotion 검증, 유료 모델 의미 품질은 서로 다른 관문이다.

### #127 worker 입력과 호출 경계

진입 함수는 `knowledge_extraction.enqueue(engine, source_document_id, options)`와 `run_task(engine, task_id, models, options)`다. 외부에서 준비한 실제 source_document를 사용하며 실행기가 문서를 수집하거나 제품 fixture를 자동 적재하지 않는다. 반환 값은 task 상태·적용된 Claim ID·제외 code이며 raw 모델 payload가 아니다. RUNNING은 lease 또는 결과 불명 slot이 남아 있을 수 있다는 뜻이며 다음 호출 가능 여부는 DB 상태·시각으로 확인한다. 요청자가 실제 유료 호출과 실행 예산을 승인하기 전에는 이 함수를 유료 provider로 실행하지 않는다.

`WorkerOptions`는 실행별 허용 request/token/candidate 예산을 명시하고, 결과에 영향을 주는 옵션·문서·정확한 ontology revision·validator·helper prompt/schema를 effective input hash에 반영한다. ModelStudio는 한 실행의 client와 Budget을 소유하므로 다음 retry 실행에는 새 인스턴스를 전달한다. 실행 오류로 중단된 Budget을 임의로 초기화하지 않는다. 같은 cache key의 성공 작업은 provider를 다시 호출하지 않는다. FINAL_FAILED의 명시적 수동 재처리는 `manual_from_task_id`와 비어 있지 않은 새 `execution_generation`을 함께 사용한다.

실제 active `KNOWLEDGE_EXTRACTION` 출력 schema가 `KnowledgeProposals`와 일치해야 한다. 이번 validator 버전은 `ke127-validator-v1`이고 지원하는 영속 lint rule은 PRE_PROMOTION/BOTH 범위의 BLOCKING `EVIDENCE_TRACE_COMPLETE`다. 알려지지 않은 active 정책을 실행한 것으로 가장하지 않고 설정 오류로 차단한다. #126 승인 allowlist와 실제 active revision이 모두 맞는 관계·속성만 사용한다. 누락 code는 반환 진단에 포함하며 출력 계약·지원 정책·사용할 ontology 자체가 없으면 enqueue가 실패한다. 이 reference data는 제품/개발 DB에 등록됐다고 가정하지 않으며 별도 등록 절차를 이 worker에 숨기지 않는다.

`server/tests/test_knowledge_extraction_postgres.py`는 `_ke127_test` loopback DB의 권한으로 임의 이름의 별도 시험 DB를 만들고 현재 migration과 합성 reference data만 적용한다. 실제 ModelStudio/LangChain HTTP 경계는 MockTransport로 대체한다. 성공·idempotency·정합화·직접 근거·부분 차단·재처리·DB rollback·늦은 응답의 lease 차단을 검증하고 생성한 DB만 제거한다. 실제 API/화면 publication이나 모델 품질 평가가 아니다.''')
q.write_text(s)
q=p/'docs/data/logical-schema.md'
s=q.read_text().replace('실제 모델·prompt 계보와 기존 작업 종류의 매핑은 제품 adapter 구현 전에 검토한다.','현재 #127은 지식 생성 호출 하나를 durable KNOWLEDGE_EXTRACTION에 대응시키고 본문 선택·자기 근거·의미 연결·동일 대상·Claim 재사용 판정은 runtime helper로 유지한다. 다른 작업 종류의 실제 worker 구현 여부는 각 소유 Issue를 따른다.')
q.write_text(s)
q=p/'docs/development/implementation-stack.md'
s=q.read_text()
s+='''

## #127 durable extraction 실행 경계

`knowledge_extraction.enqueue`와 `run_task`는 위에 고정된 Python·SQLAlchemy·LangChain·ModelStudio 버전을 재사용한다. 추가 dependency, LangGraph, memory와 별도 orchestration framework는 도입하지 않는다. `model_studio.call`의 generation 전용 `before_send` hook은 request 구성·exact endpoint/크기 검사를 마친 HTTP 전송 직전에 durable slot 예약을 commit한다. SDK 자체 retry는 계속 0이며 task 재실행이 실제 slot 예산을 소유한다.

`extraction`의 기존 runtime 하네스와 제품 task 상태는 별개다. 하네스의 process-local cache를 durable SUCCESS payload cache로 사용하지 않는다. `run_task`는 실제 active DB 계약과 #128 runtime helper를 연결해 검증된 기준 지식을 promotion COMMITTED까지 저장한다. 기존 HTTP GET은 provider를 실행하지 않으며 publication·READY와 실제 모델 품질은 별도 책임이다. 등록·검증 경계는 [DB 운영](../operations/database.md)을 따른다.
'''
q.write_text(s)
