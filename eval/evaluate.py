"""Golden Set(`eval/golden_set.jsonl`) 기반 Retrieval/Answer 품질 평가.

rag/retriever.py의 retrieve()와 rag/pipeline.py의 answer_question()이
구현된 뒤 실행한다 (tasks.md Phase 1~8 선행 필요).

    uv run python -m eval.evaluate
    uv run python -m eval.evaluate --top-k 10 --skip-answers
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Callable

from rag import pipeline, retriever

GOLDEN_SET_PATH = Path(__file__).parent / "golden_set.jsonl"
DEFAULT_TOP_K = 5


@dataclass
class GoldenItem:
    id: str
    question: str
    expected_articles: list[str]
    expected_answer_keywords: list[str]


def load_golden_set(path: Path = GOLDEN_SET_PATH) -> list[GoldenItem]:
    items = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            items.append(
                GoldenItem(
                    id=raw.get("id", ""),
                    question=raw["question"],
                    expected_articles=raw.get("expected_articles", []),
                    expected_answer_keywords=raw.get("expected_answer_keywords", []),
                )
            )
    return items


def _normalize_article(value: str | int) -> str:
    """'제2조' / 2 / '17의2' 등 서로 다른 조문 표기를 비교 가능한 키로 변환한다."""
    return str(value).replace("제", "").replace("조", "").strip()


def evaluate_retrieval(
    golden_set: list[GoldenItem],
    retrieve_fn: Callable[[str, int], list],
    k: int = DEFAULT_TOP_K,
) -> dict:
    """Golden Set 전체에 대해 Hit@K, Recall@K, MRR을 계산한다.

    retrieve_fn은 (question, top_k) -> list[RetrievedChunk] 형태여야 하며,
    각 RetrievedChunk는 `.chunk.article_no` 속성을 가져야 한다(design.md §3).
    """
    hits, recalls, reciprocal_ranks = [], [], []

    for item in golden_set:
        expected = {_normalize_article(a) for a in item.expected_articles}
        retrieved = retrieve_fn(item.question, k)
        retrieved_keys = [_normalize_article(r.chunk.article_no) for r in retrieved]

        found = expected & set(retrieved_keys)
        hits.append(1.0 if found else 0.0)
        recalls.append(len(found) / len(expected) if expected else 0.0)

        rank = next((i + 1 for i, key in enumerate(retrieved_keys) if key in expected), None)
        reciprocal_ranks.append(1 / rank if rank else 0.0)

    return {
        "hit_at_k": mean(hits) if hits else 0.0,
        "recall_at_k": mean(recalls) if recalls else 0.0,
        "mrr": mean(reciprocal_ranks) if reciprocal_ranks else 0.0,
        "k": k,
        "n": len(golden_set),
    }


def evaluate_answers(
    golden_set: list[GoldenItem],
    answer_fn: Callable[[str], object],
) -> dict:
    """정답성ㆍ근거 충실성의 근사 지표를 계산한다.

    LLM-as-judge 없이도 동작하도록, 생성된 답변 텍스트에
    expected_answer_keywords가 포함된 비율과, sources에 기대 조문이
    실제로 포함되는지(근거 충실성 근사치)를 사용한다.
    answer_fn은 question -> AnswerResult(answer, sources)를 반환해야 한다
    (rag/pipeline.py, design.md §2.6).
    """
    keyword_coverages, grounded_flags = [], []

    for item in golden_set:
        result = answer_fn(item.question)

        if item.expected_answer_keywords:
            hit_count = sum(1 for kw in item.expected_answer_keywords if kw in result.answer)
            keyword_coverages.append(hit_count / len(item.expected_answer_keywords))

        expected = {_normalize_article(a) for a in item.expected_articles}
        source_keys = {_normalize_article(s.article) for s in result.sources}
        grounded_flags.append(1.0 if expected & source_keys else 0.0)

    return {
        "answer_keyword_coverage": mean(keyword_coverages) if keyword_coverages else 0.0,
        "source_grounded_rate": mean(grounded_flags) if grounded_flags else 0.0,
        "n": len(golden_set),
    }


def compare_retrieval_configs(golden_set: list[GoldenItem], k: int = DEFAULT_TOP_K) -> dict:
    """baseline(Dense만)과 advanced(Multi Query + Hybrid) 설정의 Retrieval 지표를 비교한다."""
    configs: dict[str, Callable[[str, int], list]] = {
        "baseline (dense only)": lambda q, top_k: retriever.retrieve(q, top_k=top_k),
        "advanced (multi-query + hybrid)": lambda q, top_k: retriever.retrieve(
            q, top_k=top_k, use_multi_query=True, use_hybrid=True
        ),
    }
    return {name: evaluate_retrieval(golden_set, fn, k=k) for name, fn in configs.items()}


def _print_retrieval_report(results: dict) -> None:
    print(f"{'설정':38s} {'Hit@K':>8s} {'Recall@K':>10s} {'MRR':>8s}")
    for name, metrics in results.items():
        print(
            f"{name:38s} {metrics['hit_at_k']:8.3f} "
            f"{metrics['recall_at_k']:10.3f} {metrics['mrr']:8.3f}"
        )


def _print_answer_report(metrics: dict) -> None:
    print(
        f"answer_keyword_coverage={metrics['answer_keyword_coverage']:.3f}  "
        f"source_grounded_rate={metrics['source_grounded_rate']:.3f}  "
        f"(n={metrics['n']})"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Golden Set 기반 RAG 평가")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument(
        "--skip-answers",
        action="store_true",
        help="LLM 답변 생성(근거 충실성 평가)을 건너뛰고 Retrieval 지표만 계산한다",
    )
    args = parser.parse_args()

    golden_set = load_golden_set()

    print(f"=== Retrieval 평가 (K={args.top_k}, N={len(golden_set)}) ===")
    retrieval_results = compare_retrieval_configs(golden_set, k=args.top_k)
    _print_retrieval_report(retrieval_results)

    if not args.skip_answers:
        print("\n=== Answer 평가 ===")
        answer_results = evaluate_answers(golden_set, pipeline.answer_question)
        _print_answer_report(answer_results)


if __name__ == "__main__":
    main()
