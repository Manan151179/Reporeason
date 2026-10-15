# Import sys and os so we can add the project root to the import path
import sys
import os

# Add the project root to sys.path so imports work from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import json to load repos and save results
import json

# Import csv to read the labeled data
import csv

# Import re to tokenize text for BM25
import re

# Import BM25Okapi for keyword-based ranking
from rank_bm25 import BM25Okapi

# Import our evaluation metrics
from c3.metrics import precision_at_k, recall_at_k, mrr, ndcg_at_k


# --- Helper: tokenize text by lowercasing and splitting on non-alphanumeric ---

def tokenize(text):
    return re.split(r"[^a-z0-9]+", text.lower())


# --- Ranker A: GitHub native order (keep repos as they are) ---

def rank_github_native(repos):
    """Return full_names in the order they appear in repos.json."""
    return [repo["full_name"] for repo in repos]


# --- Ranker B: BM25 ranking against the query ---

def rank_bm25(query, repos):
    """
    Rank repos by BM25 relevance of the query against each repo's text.
    Text = name + description + topics joined with spaces.
    """
    # Build a document for each repo from its metadata
    corpus = []
    for repo in repos:
        name = repo.get("full_name") or ""
        desc = repo.get("description") or ""
        topics = " ".join(repo.get("topics") or [])
        doc_text = f"{name} {desc} {topics}"
        corpus.append(tokenize(doc_text))

    # Build the BM25 index
    bm25 = BM25Okapi(corpus)

    # Tokenize the query
    query_tokens = tokenize(query)

    # Score each repo
    scores = bm25.get_scores(query_tokens)

    # Pair each repo's full_name with its score
    scored = []
    for i, repo in enumerate(repos):
        scored.append((repo["full_name"], float(scores[i])))

    # Sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)

    # Return just the full_names, best first
    return [name for name, _ in scored]


# --- Main ---

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
            # Treat empty or missing relevance as 0
            rel_str = row.get("relevance", "").strip()
            rel = int(rel_str) if rel_str else 0

            if qid not in labels:
                labels[qid] = {}
            labels[qid][name] = rel

    print(f"Loaded labels for {len(labels)} queries from {labels_path}\n")

    # --- Run both rankers on each query and compute metrics ---

    # Accumulators for averaging
    metric_names = ["P@5", "R@10", "MRR", "nDCG@10"]
    a_totals = {m: 0.0 for m in metric_names}
    b_totals = {m: 0.0 for m in metric_names}
    per_query_results = []
    num_queries = 0

    # Print table header
    print(f"{'qid':<6}  {'Ranker':<10}  {'P@5':>6}  {'R@10':>6}  {'MRR':>6}  {'nDCG@10':>8}")
    print("-" * 52)

    for qid in sorted(all_repos.keys()):
        query_text = all_repos[qid]["query"]
        repos = all_repos[qid]["repos"]
        query_labels = labels.get(qid, {})

        print(f"\n[{qid}] \"{query_text[:50]}...\"")

        # Skip if there are no repos for this query
        if not repos:
            print(f"  (no repos, skipping)")
            continue

        num_queries += 1

        # --- Ranker A: GitHub native order ---
        ranked_a = rank_github_native(repos)

        a_p5 = precision_at_k(ranked_a, query_labels, k=5)
        a_r10 = recall_at_k(ranked_a, query_labels, k=10)
        a_mrr = mrr(ranked_a, query_labels)
        a_ndcg = ndcg_at_k(ranked_a, query_labels, k=10)

        print(f"  {'A-GitHub':<10}  {a_p5:>6.4f}  {a_r10:>6.4f}  {a_mrr:>6.4f}  {a_ndcg:>8.4f}")

        a_totals["P@5"] += a_p5
        a_totals["R@10"] += a_r10
        a_totals["MRR"] += a_mrr
        a_totals["nDCG@10"] += a_ndcg

        # --- Ranker B: BM25 ---
        ranked_b = rank_bm25(query_text, repos)

        b_p5 = precision_at_k(ranked_b, query_labels, k=5)
        b_r10 = recall_at_k(ranked_b, query_labels, k=10)
        b_mrr = mrr(ranked_b, query_labels)
        b_ndcg = ndcg_at_k(ranked_b, query_labels, k=10)

        print(f"  {'B-BM25':<10}  {b_p5:>6.4f}  {b_r10:>6.4f}  {b_mrr:>6.4f}  {b_ndcg:>8.4f}")

        b_totals["P@5"] += b_p5
        b_totals["R@10"] += b_r10
        b_totals["MRR"] += b_mrr
        b_totals["nDCG@10"] += b_ndcg

        # Save per-query detail
        per_query_results.append({
            "query_id": qid,
            "query": query_text,
            "A": {"P@5": a_p5, "R@10": a_r10, "MRR": a_mrr, "nDCG@10": a_ndcg},
            "B": {"P@5": b_p5, "R@10": b_r10, "MRR": b_mrr, "nDCG@10": b_ndcg},
        })

    # --- Compute and print averages ---

    print("\n" + "=" * 52)
    print("AVERAGES across all queries:\n")
    print(f"{'Ranker':<12}  {'P@5':>6}  {'R@10':>6}  {'MRR':>6}  {'nDCG@10':>8}")
    print("-" * 44)

    a_avg = {m: a_totals[m] / num_queries for m in metric_names}
    b_avg = {m: b_totals[m] / num_queries for m in metric_names}

    print(f"{'A-GitHub':<12}  {a_avg['P@5']:>6.4f}  {a_avg['R@10']:>6.4f}  "
          f"{a_avg['MRR']:>6.4f}  {a_avg['nDCG@10']:>8.4f}")
    print(f"{'B-BM25':<12}  {b_avg['P@5']:>6.4f}  {b_avg['R@10']:>6.4f}  "
          f"{b_avg['MRR']:>6.4f}  {b_avg['nDCG@10']:>8.4f}")

    # --- Save results to JSON ---

    output = {
        "num_queries": num_queries,
        "averages": {
            "A_GitHub": a_avg,
            "B_BM25": b_avg,
        },
        "per_query": per_query_results,
    }

    results_path = os.path.join("c3", "data", "baseline_results.json")
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"\nResults saved to {results_path}")


if __name__ == "__main__":
    main()
