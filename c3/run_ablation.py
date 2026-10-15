# Import sys and os so we can add the project root to the import path
import sys
import os

# Add the project root to sys.path so imports work from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import json to load repos and save results
import json

# Import csv to read the labeled data
import csv

# Import the hybrid ranker (accepts a custom weights dict)
from c3.rankers import rank_hybrid

# Import nDCG metric
from c3.metrics import ndcg_at_k


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

    # --- Define the ablation configurations ---

    # The full hybrid weights for reference
    full = {
        "semantic":      0.55,
        "popularity":    0.15,
        "recency":       0.15,
        "documentation": 0.10,
        "license":       0.05,
    }

    # Each config: (name, weights dict)
    # Semantic-only and full hybrid first, then leave-one-out variants
    configs = [
        ("Semantic only", {
            "semantic": 1.0, "popularity": 0.0, "recency": 0.0,
            "documentation": 0.0, "license": 0.0,
        }),
        ("Full hybrid", dict(full)),
        ("No popularity", {**full, "popularity": 0.0}),
        ("No recency",    {**full, "recency": 0.0}),
        ("No documentation", {**full, "documentation": 0.0}),
        ("No license",    {**full, "license": 0.0}),
    ]

    # --- Run each configuration across all queries ---

    sorted_qids = sorted(all_repos.keys())
    results_table = []

    for ci, (config_name, weights) in enumerate(configs):
        print(f"[{ci + 1}/{len(configs)}] Running: {config_name} ...")

        ndcg_sum = 0.0
        p5s_sum = 0.0
        num_queries = 0

        for qid in sorted_qids:
            query_text = all_repos[qid]["query"]
            repos = all_repos[qid]["repos"]
            query_labels = labels.get(qid, {})

            if not repos:
                continue

            num_queries += 1

            # Run the hybrid ranker with this config's weights
            names, _ = rank_hybrid(query_text, repos, weights=weights)

            # Compute metrics
            ndcg_val = ndcg_at_k(names, query_labels, k=10)
            p5s_val = precision_at_k_strict(names, query_labels, k=5)

            ndcg_sum += ndcg_val
            p5s_sum += p5s_val

        # Average across queries
        avg_ndcg = ndcg_sum / num_queries if num_queries > 0 else 0.0
        avg_p5s = p5s_sum / num_queries if num_queries > 0 else 0.0

        results_table.append({
            "config": config_name,
            "weights": weights,
            "avg_nDCG@10": avg_ndcg,
            "avg_P@5(strict)": avg_p5s,
        })

        print(f"  → nDCG@10={avg_ndcg:.4f}  P@5(strict)={avg_p5s:.4f}")

    # --- Print the summary table ---

    print("\n" + "=" * 55)
    print("ABLATION RESULTS\n")

    header = f"{'Configuration':<20}  {'nDCG@10':>8}  {'P@5(strict)':>12}"
    print(header)
    print("-" * len(header))

    for row in results_table:
        print(f"{row['config']:<20}  {row['avg_nDCG@10']:>8.4f}  {row['avg_P@5(strict)']:>12.4f}")

    # --- Save results to JSON ---

    output = {
        "configurations": [
            {
                "config": r["config"],
                "weights": r["weights"],
                "avg_nDCG@10": r["avg_nDCG@10"],
                "avg_P@5(strict)": r["avg_P@5(strict)"],
            }
            for r in results_table
        ],
    }

    results_path = os.path.join("c3", "data", "ablation_results.json")
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"\nResults saved to {results_path}")


if __name__ == "__main__":
    main()
