# Requirements — AI기본법 RAG QA 백엔드

## 0. 배경

- **미션**: AI 기본법을 잘 모르는 사용자도 질문을 통해 쉽게 내용을 이해할 수 있는, 근거 기반 AI 기본법 QA 백엔드 서비스를 구현한다.
- **대상 데이터**: `data/ai_basic_law.hwpx` — 인공지능 발전과 신뢰 기반 조성 등에 관한 기본법(약칭: 인공지능기본법) [시행 2026.7.21.] [법률 제21311호, 2026.1.20., 일부개정]. 6개 장(총칙 / 추진체계 / 기술개발·산업육성 / 윤리·신뢰성 확보 / 보칙 / 벌칙), 조문 번호 제1조~제43조(가지번호 조문 제17조의2·제22조의2·제22조의3 포함 총 46개 조문) + 부칙으로 구성되며 장 > 조 > 항(①②③) > 호(1.2.3.) > 목(가.나.다.)의 명확한 법률 구조를 가진다(design.md §2.2 실측 확인).
- **원본 RFP**: `요구사항/ai기본법_RAG_서비스구현.pdf`
- **기준 산출물**: `POST /ask` 단일 API. 입력은 자연어 질문, 출력은 `answer` + `sources`(근거 조문 목록).
- **핵심 평가 축**: 코드량이 아니라 "이 답변의 근거가 무엇인가 / 검색이 제대로 되었는가 / 개선이 실제로 효과가 있었는가"를 설명할 수 있는 시스템인지.

용어: SHALL(필수), SHOULD(권장), MAY(선택). 각 조항은 `rag_minipjt` 템플릿의 모듈(`rag/loader.py`, `rag/chunker.py`, `rag/vectorstore.py`, `rag/retriever.py`, `rag/reranker.py`, `rag/pipeline.py`, `app/main.py`, `eval/`)과 매핑된다.

---

## 1. 문서 로딩 (Document Loading)

**User Story**: 개발자로서, 나는 hwpx 형식의 법률 원문을 손실 없이 읽어 들여서, 이후 구조 분석과 Chunking의 입력으로 쓸 수 있기를 원한다.

### Acceptance Criteria
1. WHEN `data/ai_basic_law.hwpx` 경로가 주어지면 THE 시스템은 문서 전체 텍스트를 단락(paragraph) 단위로 손실 없이 추출해야 한다(SHALL).
2. THE 시스템은 표지·목차·이미지 캡션 등 법률 본문이 아닌 요소(OCR 캡션, QR 이미지 설명 등)를 본문 조항과 구분하여 제거하거나 별도 표시해야 한다(SHALL).
3. WHEN 로딩이 완료되면 THE 시스템은 "장 제목 / 조 제목 / 항 기호(①②③) / 호 번호(1.2.3.) / 목 기호(가.나.다.)"가 원문 그대로 보존된 순수 텍스트(또는 구조화 가능한 중간 표현)를 산출해야 한다(SHALL).
4. IF 원본 파일을 읽을 수 없거나 형식이 손상된 경우 THEN 시스템은 명확한 예외를 발생시키고 처리를 중단해야 한다(SHALL).
5. THE 시스템은 `rag/loader.py`에서 로딩 책임을 단일 진입점(예: `load_law_document(path) -> str | list[str]`)으로 제공해야 한다(SHALL).

---

## 2. 법률 구조 분석 및 Chunking

**User Story**: RAG 개발자로서, 나는 법률 문서를 "장-조-항-호" 구조를 보존한 채 검색에 적합한 크기로 쪼개서, 검색 결과가 특정 조문 단위로 깔끔하게 반환되기를 원한다.

### Acceptance Criteria
1. THE 시스템은 로딩된 텍스트에서 정규식 또는 규칙 기반으로 "제N장", "제N조(제목)", "①②③…", "1. 2. 3. …", "가. 나. 다. …" 패턴을 인식하여 계층 구조를 파악해야 한다(SHALL).
2. THE 시스템은 원칙적으로 **조(article) 단위**를 1차 Chunk 경계로 사용해야 한다(SHALL). 단, 제2조(정의)처럼 호·목이 많아 1개 조문이 지나치게 길어지는 경우(기준치 초과, 예: 1,500자 초과) THE 시스템은 항 또는 호 단위로 하위 분할해야 한다(SHALL).
3. WHEN Chunk가 생성되면 THE 시스템은 각 Chunk에 다음 메타데이터를 첨부해야 한다(SHALL): `chapter_no`, `chapter_title`, `article_no`, `article_title`, `clause_no`(하위 분할된 경우만 — 항 분할이면 "①" 등, 호 분할이면 "1호" 등, design.md §2.2 참고), `law_name`(인공지능기본법), `law_number`(법률 제21311호), `enforcement_date`(2026-07-21). 항과 호를 별도 필드로 두지 않고 `clause_no` 하나로 표현한다 — 실측 결과 한 조문 안에서 항 분할과 호 분할이 동시에 필요한 경우는 없었다(design.md §2.2).
4. THE 시스템은 부칙(법률 제21311호, 2026.1.20.)도 동일한 체계로 Chunk화해야 한다(SHALL).
5. THE 시스템은 하나의 Chunk가 둘 이상의 조문에 걸쳐 내용을 섞지 않아야 한다(SHALL) — 즉 Chunk 경계는 반드시 조(또는 그 하위) 경계와 일치해야 한다.
6. THE 시스템은 `rag/chunker.py`에서 Chunking 책임을 단일 진입점(예: `chunk_law_document(paragraphs) -> list[Chunk]`)으로 제공해야 한다(SHALL).

---

## 3. Embedding 및 Qdrant 저장 (Indexing)

**User Story**: 나는 생성된 Chunk들을 벡터로 변환하여 Qdrant에 저장함으로써, 질문이 들어왔을 때 의미 기반 검색이 가능하기를 원한다.

### Acceptance Criteria
1. THE 시스템은 `common/ai_model.get_embedding_model()`이 제공하는 Embedding 모델을 사용하여 각 Chunk의 본문 텍스트를 벡터로 변환해야 한다(SHALL).
2. THE 시스템은 `common/qdrant.get_qdrant_client()`를 통해 얻은 클라이언트로 지정된 Collection에 (vector, payload) 쌍을 저장해야 한다(SHALL). payload에는 §2.3의 메타데이터 전체와 원문 텍스트가 포함되어야 한다(SHALL).
3. WHEN Collection이 존재하지 않으면 THE 시스템은 Embedding 모델의 차원 수(dimension)에 맞춰 Collection을 자동 생성해야 한다(SHALL).
4. THE 시스템은 동일한 법률 문서를 재색인할 때 중복 Point가 쌓이지 않도록 결정론적 ID(예: 조-항-호 조합 기반 ID 또는 UUID5)를 사용해야 한다(SHOULD).
5. THE 시스템은 `rag/vectorstore.py`에서 색인 책임을 단일 진입점(예: `build_vectorstore(chunks)` / `upsert_chunks(chunks)`)으로 제공해야 한다(SHALL).
6. IF Hybrid Search(요구사항 §5)를 지원하는 경우 THEN 시스템은 Dense 벡터 외 Sparse(BM25 계열) 벡터 또는 동등한 키워드 인덱스도 함께 저장해야 한다(SHOULD). 본 프로젝트는 Hybrid Search를 1순위 기법으로 채택 확정했으므로(§5.1, design.md §2.4) 본 조항이 실제로 적용된다 — `rank_bm25` 기반 인메모리 인덱스로 구현한다(Qdrant 벡터 재구성 불필요).

---

## 4. Query 처리 및 기본 Retrieval

**User Story**: 사용자로서, 나는 자연어로 질문을 입력하면 관련된 법률 조항을 찾아주기를 원한다.

### Acceptance Criteria
1. WHEN 사용자 질문 문자열이 주어지면 THE 시스템은 동일한 Embedding 모델로 질문을 벡터화해야 한다(SHALL).
2. THE 시스템은 질문 벡터로 Qdrant Collection을 검색하여 Top-K(기본값 K, 설정 가능) 후보 Chunk를 유사도 점수와 함께 반환해야 한다(SHALL).
3. THE 시스템은 검색 결과 각 항목에 대해 원문 텍스트와 §2.3 메타데이터(조문 번호 등 근거 식별자)를 함께 반환해야 한다(SHALL).
4. THE 시스템은 `rag/retriever.py`에서 기본 Retrieval 진입점(예: `retrieve(query, top_k) -> list[RetrievedChunk]`)을 제공해야 한다(SHALL).
5. IF Qdrant 연결에 실패하면 THEN 시스템은 명확한 오류를 반환하고 빈 결과로 조용히 실패하지 않아야 한다(SHALL).

---

## 5. 검색 품질 개선 (Advanced RAG)

**User Story**: 나는 기본 Dense Retrieval만으로 놓치는 질문(용어 매칭, 다의적 질의 등)을 보완하기 위해 최소 1개 이상의 Advanced RAG 기법을 적용하고, 그 효과를 비교하고 싶다.

### Acceptance Criteria
1. THE 시스템은 RFP에서 제시된 기법(Multi Query, Hybrid Search, BM25, RRF, Metadata Filtering) 중 **최소 1개 이상**을 선택하여 구현해야 한다(SHALL). 여러 기법을 모두 구현하는 것은 MAY(선택)이며 과다 적용보다 효과 검증이 우선한다. **채택 확정(Phase 0.3, design.md §2.4)**: 1순위 Hybrid Search(Dense+BM25)+RRF, 2순위(여유 시) Metadata Filtering, 3순위(보류) Multi Query — 법률 용어·조문 번호의 정확한 매칭이 중요한 도메인 특성과 구현 비용을 근거로 결정했다.
2. IF Multi Query를 적용하는 경우 THEN 시스템은 LLM으로 원 질문의 변형 질의(N개)를 생성하고, 각 질의의 검색 결과를 합쳐 중복을 제거해야 한다(SHALL).
3. IF Hybrid Search(Dense + BM25)를 적용하는 경우 THEN 시스템은 두 검색 결과를 RRF(Reciprocal Rank Fusion) 또는 동등한 점수 융합 방식으로 결합해야 한다(SHALL).
4. IF Metadata Filtering을 적용하는 경우 THEN 시스템은 질문에서 특정 장/조 번호 등이 식별될 때 Qdrant payload 필터를 적용하여 검색 범위를 좁힐 수 있어야 한다(SHOULD).
5. THE 시스템은 적용한 기법을 끄고 켤 수 있도록(baseline vs 개선) 구성 가능해야 한다(SHALL) — Evaluation(§9)에서 Before/After 비교에 사용하기 위함이다.
6. THE 시스템은 검색 개선 로직을 `rag/retriever.py`에 위치시켜야 한다(SHALL).

---

## 6. Reranking

**User Story**: 나는 1차 검색으로 모은 후보군의 순서를 질문과의 관련성 기준으로 다시 정렬하여, 최종적으로 LLM에 전달되는 Context 품질을 높이고 싶다.

### Acceptance Criteria
1. WHEN 1차 검색 결과(Top-K, K ≥ 최종 사용 개수)가 주어지면 THE 시스템은 재정렬 로직을 거쳐 최종 Top-N(N ≤ K)을 선정해야 한다(SHALL).
2. THE 시스템은 Reranking 전/후 순서 변화를 로그 또는 중간 결과로 확인할 수 있어야 한다(SHOULD) — 효과 검증 목적.
3. THE 시스템은 `rag/reranker.py`에서 Reranking 진입점(예: `rerank(query, candidates, top_n) -> list[RetrievedChunk]`)을 제공해야 한다(SHALL).
4. IF Reranking 모델/API 호출이 실패하면 THEN 시스템은 1차 검색 순서를 fallback으로 사용해야 한다(SHOULD).

---

## 7. 근거 기반 답변 생성 (Grounded Answer)

**User Story**: 사용자로서, 나는 질문에 대한 답변뿐 아니라 그 답변이 어떤 조문을 근거로 하는지 함께 확인하고 싶다.

### Acceptance Criteria
1. THE 시스템은 최종 선정된 Chunk들만을 Context로 LLM에 전달해야 하며, LLM이 Context 밖의 일반 지식으로 단독 답변하지 않도록 프롬프트에서 명시적으로 제약해야 한다(SHALL).
2. THE 시스템은 LLM 호출에 `common/ai_model.get_llm_model()`을 사용해야 한다(SHALL).
3. WHEN 답변이 생성되면 THE 시스템은 자연어 `answer`와, 근거로 사용된 조문 목록(`sources`: 각 항목은 최소 `article`, `content` 포함)을 함께 반환해야 한다(SHALL).
4. IF 검색된 Context가 질문과 관련이 없거나 비어 있는 경우 THEN 시스템은 "근거를 찾을 수 없다"는 취지로 답변하고 근거 없는 추측 답변을 생성하지 않아야 한다(SHALL).
5. THE 시스템은 `rag/pipeline.py`에서 Retrieval → Reranking → Context 구성 → LLM 호출 → Answer+Source 조립의 전체 흐름을 단일 진입점(`answer_question(question) -> AnswerResult`)으로 제공해야 한다(SHALL). `AnswerResult`는 FastAPI/Pydantic에 의존하지 않는 순수 dataclass이며, `app/main.py`가 이를 HTTP 응답(`AskResponse`)으로 변환한다 — `rag/`가 `app/`을 참조하지 않는 의존 방향 원칙(design.md §1.1) 때문이다.

---

## 8. API (FastAPI)

**User Story**: 클라이언트 개발자로서, 나는 HTTP API 하나로 질문을 보내고 근거가 포함된 답변을 받고 싶다.

### Acceptance Criteria
1. THE 시스템은 `app/main.py`에 `POST /ask` 엔드포인트를 제공해야 한다(SHALL).
2. THE 엔드포인트는 요청 본문 `{"question": string}`을 받아야 한다(SHALL).
3. THE 엔드포인트는 응답으로 `{"answer": string, "sources": [{"article": string, "content": string}, ...]}` 형식을 반환해야 한다(SHALL) — RFP 명시 스펙과 일치.
4. IF `question`이 비어 있거나 누락된 경우 THEN 시스템은 4xx 오류를 반환해야 한다(SHALL).
5. IF 파이프라인 내부(LLM/Qdrant 등) 오류가 발생하면 THEN 시스템은 500번대 오류와 함께 원인을 식별 가능한 메시지를 반환해야 한다(SHALL) — 단, 내부 시크릿(API Key 등)은 노출하지 않아야 한다(SHALL).
6. THE 시스템은 `GET /` 또는 `/health`로 서비스 상태를 확인할 수 있어야 한다(SHOULD).
7. THE API는 자동 문서화(`/docs`, FastAPI 기본 제공)를 유지해야 한다(SHALL).

---

## 9. 평가 (Evaluation)

**User Story**: 나는 개선 작업(Advanced RAG, Reranking)이 실제로 검색/답변 품질을 높였는지 수치로 확인하고 싶다.

### Acceptance Criteria
1. THE 시스템은 `eval/golden_set.jsonl`에 질문-정답 근거(정답 조문 식별자, 선택적으로 기대 답변)를 담은 Golden Test Set을 보유해야 한다(SHALL). 각 레코드는 최소 `question`, `expected_articles`를 포함해야 한다(SHALL). 현재 6개 장 전체를 포괄하는 25문항이 작성되어 있다(완료).
2. THE 시스템은 `eval/evaluate.py`에서 Golden Set의 각 질문에 대해 Retrieval을 수행하고 Hit@K, Recall@K, MRR 중 최소 1개 이상의 지표를 계산해야 한다(SHALL).
3. THE 시스템은 baseline(Dense만) 대비 개선 기법 적용 후의 지표를 비교할 수 있는 형태로 결과를 출력해야 한다(SHALL) — 표, CSV, 또는 로그.
4. THE 시스템은 Answer 품질에 대해 정답성/관련성/근거 충실성/Hallucination 여부 중 최소 1개 이상을 정성적 또는 정량적으로 평가해야 한다(SHOULD).
5. THE 평가 스크립트는 재실행 가능해야 하며(반복 실행 시 동일 입력에 대해 비교 가능한 결과) 수작업 개입 없이 커맨드 한 번으로 실행되어야 한다(SHALL).

---

## 10. 비기능 요구사항

1. THE 시스템은 환경변수(`.env`, `common/config.py`)를 통해 LLM/Embedding 모델, Qdrant URL, API Key 등을 설정 가능해야 하며 코드에 하드코딩하지 않아야 한다(SHALL).
2. THE 시스템은 `common/` 모듈(config, qdrant, ai_model)을 `rag/`, `app/`, `eval/` 전역에서 재사용해야 하며 중복 구현하지 않아야 한다(SHALL).
3. THE 시스템은 `uv run uvicorn app.main:app --reload`로 로컬 구동 가능해야 한다(SHALL) — 기존 README 구동 방식과 일치.
4. THE 시스템은 Qdrant를 `docker-qdrant/docker-compose.yaml`로 로컬 기동 가능해야 한다(SHALL)(이미 구성됨, 변경 불필요).
5. THE 시스템은 신규 외부 의존성(예: `rank-bm25`, Reranker 모델/API용 라이브러리)을 `pyproject.toml`에 명시하고 `uv add`로 관리해야 한다(SHALL). **Docling은 사용하지 않는다** — hwpx가 Docling 공식 지원 포맷에 포함되지 않음을 확인했으며(design.md §2.1), 대신 표준 라이브러리 `zipfile`+`xml.etree.ElementTree`로 로딩을 구현한다.
6. THE 시스템은 법률 원문을 그대로(의역·요약 없이) Context로 사용해야 한다(SHALL) — 법률 QA의 정확성 요구 특성상 임의 축약을 금지한다.
7. THE 구현은 현재 리포지토리의 디렉터리 구조(`rag/`, `app/`, `common/`, `eval/`, `data/`, `docker-qdrant/`)를 그대로 유지해야 한다(SHALL) — 새 모듈은 템플릿이 정의한 기존 파일(`loader.py`, `chunker.py`, `vectorstore.py`, `retriever.py`, `reranker.py`, `pipeline.py`, `app/main.py`, `eval/evaluate.py`) 안에 구현하며, 임의로 디렉터리를 재구성하거나 최상위에 새 폴더를 추가하지 않아야 한다.
8. THE 구현은 가독성과 유지보수성을 기능 추가보다 우선해야 한다(SHALL) — 모듈(파일)당 단일 책임을 유지하고, 함수는 하나의 작업 단위로 작게 유지하며, 매직 넘버·하드코딩된 값은 `common/config.py` 또는 함수 인자로 노출해야 한다. 이름(변수/함수/클래스)은 축약 없이 의도가 드러나도록 작성해야 한다(SHALL).

---

## 11. 범위 외 (Out of Scope)

- 사용자 인증/권한 관리
- 프론트엔드 UI (API 레벨까지만 구현)
- AI 기본법 외 타 법령 지원
- 대화형 멀티턴 세션 관리(단발 질의응답 `/ask`만 지원)
