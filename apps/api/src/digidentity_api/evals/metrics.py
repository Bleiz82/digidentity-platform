"""Eval metrics — NDCG@k, MRR, Recall@k, latency percentiles, accuracy.

All functions are pure and side-effect-free.
"""

from __future__ import annotations

import math


def ndcg_at_k(ranked_items: list[str], relevant_items: set[str], k: int) -> float:
    """NDCG@k.

    ranked_items: ordered list of retrieved item IDs/slugs.
    relevant_items: ground-truth set of relevant item IDs/slugs.
    k: cutoff.
    """
    if not relevant_items:
        return 0.0

    def dcg(items: list[str], rel: set[str], cutoff: int) -> float:
        total = 0.0
        for i, item in enumerate(items[:cutoff]):
            if item in rel:
                # position i (0-indexed) → rank i+1 → log2(i+2)
                total += 1.0 / math.log2(i + 2)
        return total

    actual_dcg = dcg(ranked_items, relevant_items, k)

    # Ideal: place all relevant items first
    ideal_count = min(len(relevant_items), k)
    ideal_items = list(relevant_items)[:ideal_count]
    ideal_dcg = dcg(ideal_items, relevant_items, k)

    if ideal_dcg == 0.0:
        return 0.0
    return actual_dcg / ideal_dcg


def mrr(ranked_items: list[str], relevant_items: set[str]) -> float:
    """Mean Reciprocal Rank.

    Returns 1/(position of first relevant item), or 0.0 if none found.
    """
    for i, item in enumerate(ranked_items):
        if item in relevant_items:
            return 1.0 / (i + 1)
    return 0.0


def recall_at_k(ranked_items: list[str], relevant_items: set[str], k: int) -> float:
    """Recall@k = |retrieved[:k] ∩ relevant| / |relevant|."""
    if not relevant_items:
        return 0.0
    retrieved_top_k = set(ranked_items[:k])
    hits = len(retrieved_top_k & relevant_items)
    return hits / len(relevant_items)


def latency_percentiles(latencies_ms: list[float]) -> dict[str, float]:
    """Calcola P50, P95, P99 da lista di latenze in ms."""
    if not latencies_ms:
        return {"p50": 0.0, "p95": 0.0, "p99": 0.0}

    sorted_latencies = sorted(latencies_ms)
    n = len(sorted_latencies)

    def percentile(p: float) -> float:
        # Nearest-rank method
        idx = math.ceil(p / 100.0 * n) - 1
        idx = max(0, min(idx, n - 1))
        return sorted_latencies[idx]

    return {
        "p50": percentile(50),
        "p95": percentile(95),
        "p99": percentile(99),
    }


def routing_accuracy(results: list[dict]) -> float:
    """Percentage of routing cases where both complex and preferred_model are correct.

    Each result dict must have keys: correct (bool).
    """
    if not results:
        return 0.0
    correct = sum(1 for r in results if r.get("correct", False))
    return correct / len(results)


def circuit_breaker_pass_rate(results: list[dict]) -> float:
    """Percentage of circuit breaker scenarios that passed (all must be 100%).

    Each result dict must have key: passed (bool).
    """
    if not results:
        return 0.0
    passed = sum(1 for r in results if r.get("passed", False))
    return passed / len(results)
