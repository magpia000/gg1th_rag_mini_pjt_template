# Tasks — AI기본법 RAG QA 백엔드

관련 문서: [requirements.md](./requirements.md) · [design.md](./design.md)

표기: 각 태스크 끝의 `(Req x.y)`는 requirements.md의 해당 조항을 가리킨다.

## 공통 준수 사항 (모든 Phase에 적용)

- [ ] 새 디렉터리/파일을 추가하지 않고 기존 구조(`app/`, `rag/`, `common/`, `eval/`, `data/`, `docker-qdrant/`) 안에서만 구현한다 (Req 10.7, Design §1.1)
- [ ] 각 모듈 구현 후 Design §1.1 체크리스트(단일 책임 / 작은 함수 / 설정 외부화 / 명시적 이름 / 타입 힌트 / 의존 방향 / 주석 최소화)로 자체 점검한다 (Req 10.8, Design §1.1)

---

## Phase 0 — 환경 준비

- [x] 0.1 Qdrant 로컬 기동 확인: `docker compose`로 이미 기동 중 확인됨(`qdrant: Up`) (Req 10.4)
- [x] 0.2 hwpx 파싱 방식 결정(완료): Docling 공식 지원 포맷에 HWP/HWPX 없음을 확인 → **표준 라이브러리 `zipfile` + `xml.etree.ElementTree` 자체 파싱**으로 확정. 실제 파일로 511개 텍스트 노드/26,584자 추출 및 장·조·항·호·목 기호 보존을 검증 완료 (Req 1.1, Design §2.1)
- [x] 0.3 Hybrid Search 채택 여부 결정(완료): **채택** — Dense+BM25+RRF를 1순위로, Metadata Filtering을 2순위(여유 시), Multi Query는 3순위(보류)로 확정. `rank-bm25` 의존성 추가 확정, `docling`은 추가하지 않음 (Req 5.1, Design §2.4)
- [ ] 0.4 신규 의존성(`rank-bm25`) `pyproject.toml`에 추가 후 `uv sync` (Req 10.5)
- [ ] 0.5 `common/config.py`에 `QDRANT_COLLECTION`, `RETRIEVAL_TOP_K`, `RERANK_TOP_N`, `CHUNK_MAX_CHARS` 추가 (Design §4)

## Phase 1 — Document Loading (`rag/loader.py`)

- [ ] 1.1 `load_law_document(path)` 구현: hwpx → 문단 리스트 추출 (Req 1.1, 1.5)
- [ ] 1.2 표지/로고/캡션 등 비본문 블록 제거(`_strip_front_matter`) (Req 1.2)
- [ ] 1.3 장/조/항/호/목 원문 기호(①②③, 1.2.3., 가.나.다.)가 그대로 보존되는지 샘플 출력으로 확인 (Req 1.3)
- [ ] 1.4 파일 손상/경로 오류 시 예외 처리 (Req 1.4)
- [ ] 1.5 노트북(`notebook/`)에서 `load_law_document` 결과를 조 제목 20개 정도 눈으로 검증

## Phase 2 — 구조 분석 + Chunking (`rag/chunker.py`)

- [ ] 2.1 장/조/항/호/목 정규식 패턴 정의 및 단위 테스트(샘플 문자열) (Design §2.2 표)
- [ ] 2.2 `LawChunk` dataclass 정의 (Design §3)
- [ ] 2.3 조 단위 1차 Chunking 로직(state machine) 구현 (Req 2.1, 2.2, 2.5)
- [ ] 2.4 길이 임계치(1,500자) 초과 조문의 하위 분할 구현: 제22조의2(항 ①~⑫ 보유)는 항 단위, 제2조(정의, 항 없이 호 1~12만 존재)는 호 단위로 분할 — 두 경우 모두 실제 데이터로 확인된 유일한 초과 조문 (Req 2.2, Design §2.2)
- [ ] 2.5 부칙 블록 별도 처리 (Req 2.4)
- [ ] 2.6 결정론적 Chunk ID 생성 규칙 구현(uuid5 또는 "art-N[-clause-X]") (Design §2.2)
- [ ] 2.7 전체 문서에 대해 `chunk_law_document` 실행 → 조문 46개 + 부칙이 빠짐없이 Chunk화되었는지 개수 검증 (Req 2.1)

## Phase 3 — Embedding + Qdrant 저장 (`rag/vectorstore.py`)

- [ ] 3.1 `ensure_collection`: Collection 미존재 시 자동 생성(벡터 차원 probe) (Req 3.3)
- [ ] 3.2 `build_vectorstore(chunks)`: Embedding 생성 + payload 구성 + upsert (Req 3.1, 3.2, 3.5)
- [ ] 3.3 재색인 시 중복 Point 발생하지 않는지 확인(동일 ID upsert) (Req 3.4)
- [ ] 3.4 BM25 인메모리 인덱스 구축 함수 추가(`rank_bm25`, Phase 0.3 결정에 따라 채택 확정) (Req 3.6)
- [ ] 3.5 색인 배치 스크립트/노트북 셀로 전체 파이프라인(Phase1→2→3) 1회 실행 및 Qdrant Collection 내 포인트 수 확인

## Phase 4 — 기본 Retrieval (`rag/retriever.py`)

- [ ] 4.1 `retrieve_dense(query, top_k)` 구현 (Req 4.1, 4.2)
- [ ] 4.2 `RetrievedChunk` 모델 정의 (Design §3)
- [ ] 4.3 검색 결과에 원문+메타데이터(조문 식별자) 포함 확인 (Req 4.3)
- [ ] 4.4 Qdrant 연결 실패 시 예외 전파 확인(조용한 빈 결과 금지) (Req 4.5)
- [ ] 4.5 샘플 질문("고영향 인공지능이란 무엇인가요?")으로 수동 검색 테스트 → 제2조가 Top-K에 들어오는지 확인

## Phase 5 — Advanced RAG 검색 개선 (`rag/retriever.py`)

- [ ] 5.1 Hybrid Search 구현(1순위, Phase 0.3 결정): Dense + BM25 각각의 순위 리스트 생성 (Req 5.1, 5.3)
- [ ] 5.2 RRF 융합 함수 구현(Dense/BM25 두 랭킹 리스트 → 단일 랭킹, k=60) (Req 5.3)
- [ ] 5.3 `retrieve()`에 baseline/advanced 토글 플래그 추가 (Req 5.5)
- [ ] 5.4 baseline vs advanced 비교용 샘플 질의 3~5개로 수동 비교
- [ ] 5.5 (여유 시, 2순위) Metadata Filtering: 질문 내 조/장 번호 추출 → Qdrant Filter (Req 5.4)
- [ ] 5.6 (보류, 3순위 — Hybrid만으로 부족한 질문 유형이 확인되면 추가) Multi Query: LLM 질의 변형 생성 + 합집합 dedup (Req 5.2)

## Phase 6 — Reranking (`rag/reranker.py`)

- [ ] 6.1 Reranker 방식 결정(LLM 기반 scoring vs Cross-Encoder) (Design §2.5)
- [ ] 6.2 `rerank(query, candidates, top_n)` 구현 (Req 6.1, 6.3)
- [ ] 6.3 호출 실패 시 1차 순서 fallback 구현 (Req 6.4)
- [ ] 6.4 Rerank 전/후 순서 변화 로그 출력 (Req 6.2)

## Phase 7 — Grounded Answer (`rag/pipeline.py`)

- [ ] 7.1 Grounded 프롬프트(System/User) 작성 — Context 밖 지식 사용 금지 명시 (Req 7.1)
- [ ] 7.2 `_build_context(chunks)`: 조문별 텍스트를 구조화해 join (Design §2.6)
- [ ] 7.3 `_generate_answer(question, context)`: `common.ai_model.get_llm_model()` 호출 (Req 7.2)
- [ ] 7.4 Context 비어있을 때 "근거 없음" 고정 응답 + LLM 미호출 (Req 7.4)
- [ ] 7.5 `answer_question(question) -> AnswerResult` 전체 조립 — `AskResponse`(Pydantic)가 아닌 순수 dataclass 반환, 변환은 `app/main.py`에서 수행 (Req 7.3, 7.5, Design §2.6)
- [ ] 7.6 샘플 질문 end-to-end 실행 → answer + sources(article, content) 형태 확인

## Phase 8 — API (`app/main.py`)

- [ ] 8.1 `AskRequest`/`Source`/`AskResponse` Pydantic 모델 정의 (Design §2.7)
- [ ] 8.2 `POST /ask` 엔드포인트 구현, `pipeline.answer_question` 연결 (Req 8.1, 8.2, 8.3)
- [ ] 8.3 빈 question 요청 시 400 처리 (Req 8.4)
- [ ] 8.4 내부 예외 500 처리 + 시크릿 미노출 확인 (Req 8.5)
- [ ] 8.5 `GET /health` 추가(Qdrant 연결 체크) (Req 8.6)
- [ ] 8.6 `uv run uvicorn app.main:app --reload` 기동 후 `/docs`에서 수동 테스트 (Req 8.7, 10.3)

## Phase 9 — Evaluation (`eval/`)

- [x] 9.1 `eval/golden_set.jsonl` 작성: 6개 장 전체에서 총 25문항(question, expected_articles, expected_answer_keywords 포함) (Req 9.1)
- [x] 9.2 `evaluate_retrieval`: Hit@K/Recall@K/MRR 계산 구현 (`eval/evaluate.py`) (Req 9.2)
- [ ] 9.3 `compare_retrieval_configs`(baseline vs advanced)로 Phase 1~8 완료 후 실제 Qdrant 데이터로 비교 실행 및 결과 기록(`eval/results.md` 또는 콘솔 표) — 함수는 구현됨, 실행은 retriever.py 구현 후 가능 (Req 9.3)
- [x] 9.4 `evaluate_answers`: 답변 키워드 커버리지 + 근거(sources) 포함 조문 일치 여부로 정답성/근거충실성 근사 평가 로직 구현 (`eval/evaluate.py`) (Req 9.4)
- [ ] 9.5 `uv run python -m eval.evaluate` 한 번 실행으로 전체 평가가 재현되는지 확인 — Phase 1~8(특히 retriever.py의 `retrieve()`, pipeline.py의 `answer_question()`) 구현 후 가능 (Req 9.5)

> 참고: `eval/evaluate.py`는 `rag.retriever`/`rag.pipeline` **모듈**을 import하므로(심볼 직접 import 아님) 해당 파일이 빈 스텁이어도 `eval/evaluate.py` 자체의 import는 깨지지 않는다. 단, 실제 실행 시 `retriever.retrieve()` / `pipeline.answer_question()` 호출 지점에서 `AttributeError`가 발생하므로 Phase 1~8을 먼저 구현해야 한다. `load_golden_set`/`evaluate_retrieval`/`evaluate_answers`는 가짜(mock) 함수로 이미 단위 검증됨.

## Phase 10 — 마무리

- [ ] 10.1 README.md에 색인 실행 방법 + API 사용 예시(curl/HTTPie) 추가
- [ ] 10.2 `.env.example` 또는 README에 신규 환경변수(§Phase 0.5) 문서화
- [ ] 10.3 Advanced RAG 기법 적용 전/후 비교 결과를 간단한 보고 형태로 정리(어떤 기법이 왜 효과적이었는지)
- [ ] 10.4 전체 흐름(Document Processing → Retrieval → Grounded Answer → Evaluation) 재현 가능 여부 최종 점검
- [ ] 10.5 디렉터리 구조가 처음 그대로인지, 모듈별 책임 분리가 깨지지 않았는지 최종 리뷰 (Req 10.7, 10.8)
