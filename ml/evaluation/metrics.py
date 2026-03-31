"""
Ranking evaluation metrics for the plant recommender.

All functions accept lists of item IDs (or any hashable).
"""

import math


def precision_at_k(recommended: list, relevant: list, k: int) -> float:
    """Fraction of top-k recommendations that are relevant."""
    if k <= 0:
        return 0.0
    top_k = recommended[:k]
    relevant_set = set(relevant)
    hits = sum(1 for item in top_k if item in relevant_set)
    return hits / k


def recall_at_k(recommended: list, relevant: list, k: int) -> float:
    """Fraction of relevant items found in the top-k recommendations."""
    if not relevant or k <= 0:
        return 0.0
    top_k = recommended[:k]
    relevant_set = set(relevant)
    hits = sum(1 for item in top_k if item in relevant_set)
    return hits / len(relevant_set)


def dcg_at_k(recommended: list, relevant: list, k: int) -> float:
    """Discounted Cumulative Gain at k."""
    relevant_set = set(relevant)
    dcg = 0.0
    for i, item in enumerate(recommended[:k], start=1):
        if item in relevant_set:
            dcg += 1.0 / math.log2(i + 1)
    return dcg


def ideal_dcg_at_k(relevant: list, k: int) -> float:
    """Ideal DCG — all relevant items placed at the top."""
    n = min(len(relevant), k)
    return sum(1.0 / math.log2(i + 1) for i in range(1, n + 1))


def ndcg_at_k(recommended: list, relevant: list, k: int) -> float:
    """Normalised Discounted Cumulative Gain at k."""
    idcg = ideal_dcg_at_k(relevant, k)
    if idcg == 0.0:
        return 0.0
    return dcg_at_k(recommended, relevant, k) / idcg


def average_precision(recommended: list, relevant: list) -> float:
    """Average Precision across the full ranked list."""
    relevant_set = set(relevant)
    if not relevant_set:
        return 0.0
    hits = 0
    total = 0.0
    for i, item in enumerate(recommended, start=1):
        if item in relevant_set:
            hits += 1
            total += hits / i
    return total / len(relevant_set)


def evaluate_recommendations(recommended: list, relevant: list, k: int = 5) -> dict:
    """Return a summary dict of all metrics at k."""
    return {
        f'precision@{k}': precision_at_k(recommended, relevant, k),
        f'recall@{k}':    recall_at_k(recommended, relevant, k),
        f'ndcg@{k}':      ndcg_at_k(recommended, relevant, k),
        'avg_precision':  average_precision(recommended, relevant),
    }
