# Import math for the log2 function used in NDCG
import math


def precision_at_k(ranked, labels, k=5):
    """
    Fraction of the top-k ranked items that are relevant (label >= 1).
    Items not in labels are treated as relevance 0.
    """
    # Take only the first k items
    top_k = ranked[:k]

    # Count how many of them are relevant
    relevant_count = sum(1 for name in top_k if labels.get(name, 0) >= 1)

    # Precision = relevant found / k
    return relevant_count / k if k > 0 else 0.0


def recall_at_k(ranked, labels, k=10):
    """
    Of all relevant items in labels, what fraction appears in the top-k?
    Items not in labels are treated as relevance 0.
    """
    # Find all items that are relevant in the full label set
    all_relevant = [name for name, rel in labels.items() if rel >= 1]

    # If there are no relevant items at all, recall is 0
    if not all_relevant:
        return 0.0

    # Take only the first k items
    top_k = set(ranked[:k])

    # Count how many relevant items appear in the top k
    found = sum(1 for name in all_relevant if name in top_k)

    # Recall = relevant found / total relevant
    return found / len(all_relevant)


def mrr(ranked, labels):
    """
    Mean Reciprocal Rank: 1 / position of the first relevant item.
    Returns 0 if no relevant item is found in the ranked list.
    """
    # Walk through the ranked list and find the first relevant item
    for i, name in enumerate(ranked, start=1):
        if labels.get(name, 0) >= 1:
            return 1.0 / i

    # No relevant item found
    return 0.0


def ndcg_at_k(ranked, labels, k=10):
    """
    Normalized Discounted Cumulative Gain at k, using graded relevance.
    Gain = relevance value (0, 1, or 2).
    Discount = 1 / log2(rank + 1), where rank is 1-based.
    """

    # Compute DCG for the actual ranked list
    dcg = 0.0
    for i, name in enumerate(ranked[:k], start=1):
        gain = labels.get(name, 0)
        discount = math.log2(i + 1)
        dcg += gain / discount

    # Compute ideal DCG: sort all label values descending, take top k
    ideal_gains = sorted(labels.values(), reverse=True)[:k]
    idcg = 0.0
    for i, gain in enumerate(ideal_gains, start=1):
        discount = math.log2(i + 1)
        idcg += gain / discount

    # Avoid division by zero if there are no relevant items
    if idcg == 0:
        return 0.0

    # NDCG = actual DCG / ideal DCG
    return dcg / idcg


# --- Quick test with a tiny hand-made example ---

if __name__ == "__main__":

    # A ranked list of 4 repo names (best first)
    ranked_list = ["repo/A", "repo/B", "repo/C", "repo/D"]

    # Graded relevance labels: A is highly relevant, C is somewhat relevant
    label_dict = {
        "repo/A": 2,   # highly relevant
        "repo/B": 0,   # not relevant
        "repo/C": 1,   # somewhat relevant
        "repo/D": 0,   # not relevant
    }

    print("Ranked list:", ranked_list)
    print("Labels:     ", label_dict)
    print()

    # Test all four metrics at k=4 (the full list)
    p = precision_at_k(ranked_list, label_dict, k=4)
    print(f"Precision@4:  {p:.4f}   (expect 0.5000 — 2 of 4 are relevant)")

    r = recall_at_k(ranked_list, label_dict, k=4)
    print(f"Recall@4:     {r:.4f}   (expect 1.0000 — both relevant items found)")

    m = mrr(ranked_list, label_dict)
    print(f"MRR:          {m:.4f}   (expect 1.0000 — first item is relevant)")

    n = ndcg_at_k(ranked_list, label_dict, k=4)
    print(f"NDCG@4:       {n:.4f}   (expect high — best item is ranked first)")

    print()

    # Also test with k=2 to see partial results
    p2 = precision_at_k(ranked_list, label_dict, k=2)
    print(f"Precision@2:  {p2:.4f}   (expect 0.5000 — 1 of 2 is relevant)")

    r2 = recall_at_k(ranked_list, label_dict, k=2)
    print(f"Recall@2:     {r2:.4f}   (expect 0.5000 — 1 of 2 relevant items found)")

    n2 = ndcg_at_k(ranked_list, label_dict, k=2)
    print(f"NDCG@2:       {n2:.4f}   (expect high — top item is the best one)")
