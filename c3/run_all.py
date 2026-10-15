# Import sys and os so we can add the project root to the import path
import sys
import os

# Add the project root to sys.path so imports work from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import json to load repos and save results
import json

# Import csv to read the labeled data
import csv

# Import our four rankers
from c3.rankers import rank_native, rank_bm25, rank_dense, rank_hybrid

# Import our evaluation metrics
from c3.metrics import precision_at_k, recall_at_k, mrr, ndcg_at_k


# --- Helper: strict precision — fraction of top-k with label == 2 ---

def precision_at_k_strict(ranked, labels, k=5):
    """Fraction of the top-k that have graded relevance exactly 2."""
    top_k = ranked[:k]
    count = sum(1 for name in top_k if labels.get(name, 0) == 2)
    return count / k if k > 0 else 0.0


def main():
    # --- Load repos.json ---

    repos_path = os.path.join("c3", "data", "repos.json")
    with open(repos_path, "r", encoding="utf-8") as f:
        all_repos = json.load(f)

    print(f"Loaded {len(all_repos)} queries from {repos_path}")

    # --- Load labels from to_label.csv ---
    # Build a dict: query_id → {full_name → int(relevance)}

    labels_path = os.path.join("c3", "data", "to_label.csv")
    labels = {}

    with open(labels_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            qid = row["query_id"]
            name = row["full_name"]
            rel_str = row.get("relevance", "").strip()
            rel = int(rel_str) if rel_str else 0

            if qid not in labels:
                labels[qid] = {}
            labels[qid][name] = rel

    print(f"Loaded labels for {len(labels)} queries from {labels_path}\n")

    # --- Define the rankers to evaluate ---

    # Each entry: (label, name, function)
    # rank_hybrid returns (names, scored) so we wrap it
    def hybrid_wrapper(query, repos):
        names, _ = rank_hybrid(query, repos)
        return names

    rankers = [
        ("A", "Native",  rank_native),
        ("B", "BM25",    rank_bm25),
        ("C", "Dense",   rank_dense),
        ("D", "Hybrid",  hybrid_wrapper),
    ]

    # The five metrics we track
    metric_names = ["P@5", "R@10", "MRR", "nDCG@10", "P@5(strict)"]

    # Accumulators: ranker_label → {metric → total}
    totals = {r[0]: {m: 0.0 for m in metric_names} for r in rankers}
    per_query_results = []
    num_queries = 0

    # --- Evaluate each query ---

    sorted_qids = sorted(all_repos.keys())

    for qi, qid in enumerate(sorted_qids):
        query_text = all_repos[qid]["query"]
        repos = all_repos[qid]["repos"]
        query_labels = labels.get(qid, {})

        print(f"[{qi + 1}/{len(sorted_qids)}] {qid}: \"{query_text[:55]}...\"")

        if not repos:
            print("  (no repos, skipping)\n")
            continue

        num_queries += 1
        query_row = {"query_id": qid, "query": query_text}

        for label, name, ranker_fn in rankers:
            # Note: dense and hybrid call the embedding model, so they may
            # take a moment — the progress line above lets you know it's working
            ranked = ranker_fn(query_text, repos)

            p5     = precision_at_k(ranked, query_labels, k=5)
            r10    = recall_at_k(ranked, query_labels, k=10)
            m      = mrr(ranked, query_labels)
            n10    = ndcg_at_k(ranked, query_labels, k=10)
            p5s    = precision_at_k_strict(ranked, query_labels, k=5)

            print(f"  {label}-{name:<8}  P@5={p5:.4f}  R@10={r10:.4f}  "
                  f"MRR={m:.4f}  nDCG@10={n10:.4f}  P@5s={p5s:.4f}")

            totals[label]["P@5"]         += p5
            totals[label]["R@10"]        += r10
            totals[label]["MRR"]         += m
            totals[label]["nDCG@10"]     += n10
            totals[label]["P@5(strict)"] += p5s

            query_row[label] = {
                "P@5": p5, "R@10": r10, "MRR": m,
                "nDCG@10": n10, "P@5(strict)": p5s,
            }

        per_query_results.append(query_row)
        print()

    # --- Compute and print averages ---

    print("=" * 72)
    print("AVERAGES across all queries:\n")

    header = f"{'Ranker':<12}  {'P@5':>6}  {'R@10':>6}  {'MRR':>6}  {'nDCG@10':>8}  {'P@5(s)':>7}"
    print(header)
    print("-" * len(header))

    averages = {}
    for label, name, _ in rankers:
        avg = {m: totals[label][m] / num_queries for m in metric_names}
        averages[f"{label}_{name}"] = avg
        print(f"{label}-{name:<9}  {avg['P@5']:>6.4f}  {avg['R@10']:>6.4f}  "
              f"{avg['MRR']:>6.4f}  {avg['nDCG@10']:>8.4f}  {avg['P@5(strict)']:>7.4f}")

    # --- Save results to JSON ---

    output = {
        "num_queries": num_queries,
        "averages": averages,
        "per_query": per_query_results,
    }

    results_path = os.path.join("c3", "data", "all_results.json")
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"\nResults saved to {results_path}")


if __name__ == "__main__":
    main()
