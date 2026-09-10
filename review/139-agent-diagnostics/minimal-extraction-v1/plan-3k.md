## 후속 시험 계획 동결: 전체 기사 최소 runtime 출력 비교

인접 원문 ID 표시 후보를 기각한 뒤, 다음 병목인 출력 계약 복잡도를 확인한다. 원문 보존 지침은 고정하고, 사람이 focus 문장을 지정하지 않은 전체 기사에서 풍부한 진단 출력과 최소 runtime 출력을 비교한다.

### 비교 조건

- 공통 입력: 같은 전체 기사와 동일한 문장·표 행 단위의 `source_id`, 원문, 문자 위치를 제공한다.
- 공통 역할: 구체적인 지식 후보를 직접 고르고, 계획·예측·부정·발언 귀속·공동성·수량·조건·대상 범위를 보존하며, 독립 사실을 분리한다.
- 풍부한 조건: 지식 문장과 modality 외에 `critical_elements`, `main_source_ids`, `context_source_ids`를 반환한다.
- 최소 조건: 지식 문장, modality와 통합된 `source_ids`만 반환한다. 설명·판정 이유·critical element·근거 역할 구분은 반환하지 않는다.
- 두 조건 모두 판정 불가 후보는 `unresolved`의 원문 ID 묶음으로만 반환하며 통과로 계산하지 않는다.
- 두 조건 모두 strict JSON Schema를 사용한다. 이것은 앞선 호환성 시험에서 확인한 기술적 경계를 재사용하는 것이며 의미 품질을 보장하지 않는다.

### 자료와 사전 기준

- 이전 20개 기사와 URL·본문 hash가 다른 공식 한국어 기사 4건을 사용한다. 사건 계열도 수동으로 대조했다.
- SK하이닉스 제78기 정기주주총회: https://news.skhynix.co.kr/78th-annual-general-meeting/ (`b3130bf2d3810e1543ae6ea1cf56b07c8c9abcb644c42faa1d2fb5010534d076`)
- 삼성전자 2026년 1분기 실적: https://news.samsung.com/kr/%EC%82%BC%EC%84%B1%EC%A0%84%EC%9E%90-2026%EB%85%84-1%EB%B6%84%EA%B8%B0-%EC%8B%A4%EC%A0%81-%EB%B0%9C%ED%91%9C (`5bd23be82026b8d3989d1015eb05083fae2d6b91381f511dce9dcd5ae2f84ebf`)
- NVIDIA GTC 2026 한국 기업 협력: https://blogs.nvidia.co.kr/blog/gtc-2026-korea-partnership/ (`44480f45d0acc5dd60560a9a5481c4b6e08f4bbdd3605acc54a0fd67b99763b1`)
- Intel Hot Chips 2026 아키텍처: https://www.intel.co.kr/content/www/kr/ko/newsroom/news/client-computing/intel-outlines-architectures-for-agentic-ai-at-hot-chips-2026.html (`58a2802d34476ae1ea1ad6e25f1d05807f331aae067d881f8715da8b4e1bca14`)
- 모델 출력을 보기 전에 필수 사실 묶음 21개와 허용 modality, 충분한 근거 조합, 사실 분리·공동성 기준을 동결했다.
- 필수 사실은 출력된 Claim 수가 아니라 원문 기준의 고정 분모다. 어려운 사실을 생략하거나 `unresolved`로 보내 통과율을 높일 수 없다.
- 생성된 모든 Claim도 별도로 검토해 비지원 주장과 잘못된 사실 병합 비율을 확인한다.

### 호출·비용·중단

- 모델은 `qwen3.7-flash-2026-07-15`, temperature 0, thinking·streaming 비활성, 출력 상한 3,000 tokens로 고정한다.
- 기사 4건 × 조건 2개 × 반복 2회로 최대 16회 호출한다. 자동 수정·repair·재시도 호출은 없다.
- 예약 상한은 `$0.01477068`, 이번 라운드 상한은 `$0.025`, 이전 기록을 포함한 최대 누적값은 `$0.89538814 / $1.00`이다.
- 격리된 출력 또는 로컬 계약 오류는 비용과 실패를 기록하고 남은 고정 호출을 계속한다. 인증·전송·제공자 응답 형태·사용량 불명확·예산·원문 무결성 오류가 발생하면 전체 실행을 중단한다.

### 판정 기준

- 최소 조건을 다음 후보로 유지하려면 비교 가능한 기사가 최소 3건이어야 한다.
- 최소 조건의 엄격한 필수 사실 PASS가 풍부한 조건보다 최소 5개 많아야 한다.
- 최소 조건에 새 의미 변경·근거 부족·modality·귀속·사실 분리 회귀가 없어야 한다.
- 생성 Claim의 비지원 비율이 증가하지 않아야 한다.
- 기사별 필수 사실이 모두 통과한 시도도 함께 보고하지만, 이 수치만으로 독립 평가 진입을 영구적으로 막지 않는다.

### 책임과 제외 범위

- 일반 코드는 strict schema, 허용 원문 ID, 실제 원문 slice·offset·hash, 중복 ID와 계약 형태만 검사하고 의미를 자동 보충하지 않는다.
- 모델은 원문에서 지식 후보를 고르고 필요한 근거 ID와 modality를 반환한다.
- 이번 비교는 runtime 출력 후보만 판단한다. 제품 worker, 자동 저장, promotion, 운영 품질과 최종 #127 계약을 승인하지 않는다.
- 제품 코드, DB, migration, SQLAlchemy metadata, fixture, 정식 문서와 의존성은 변경하지 않는다. 원문 전문, 모델 원응답과 키는 공개 검토 패키지에 넣지 않는다.

동결 manifest SHA-256은 `375b3230088dc83460282a488cc6340a6cfce45a6ae2d2ce97476dc982f393d8`이다. 결과는 `docs/139-agent-review` 브랜치와 #139에 기록하고, #127에는 제품 계약으로 넘길 수 있는 결론만 분리해 남긴다.
