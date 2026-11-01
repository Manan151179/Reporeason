"""Evaluate GNN-enriched embeddings vs baseline on the hybrid ranker."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import csv
import numpy as np

from c3.embeddings import embed_text
from c3.rankers import repo_text, rank_hybrid
from c3.gcn import build_adjacency, gcn_enrich
from c3.metrics import precision_at_k, recall_at_k, mrr, ndcg_at_k


# Reuse run_all's strict-P@5 helper
def precision_at_k_strict(ranked, labels, k=5):
    """Fraction of the top-k that have graded relevance exactly 2."""
    top_k = ranked[:k]
    count = sum(1 for name in top_k if labels.get(name, 0) == 2)
    return count / k if k > 0 else 0.0


METRIC_NAMES = ["P@5", "R@10", "MRR", "nDCG@10", "P@5(strict)"]


def compute_metrics(ranked, labels):
    return {
        "P@5":         precision_at_k(ranked, labels, k=5),
        "R@10":        recall_at_k(ranked, labels, k=10),
        "MRR":         mrr(ranked, labels),
        "nDCG@10":     ndcg_at_k(ranked, labels, k=10),
        "P@5(strict)": precision_at_k_strict(ranked, labels, k=5),
    }


def main():
    # --- Load data ---
    repos_path = os.path.join("c3", "data", "repos.json")
    with open(repos_path, "r", encoding="utf-8") as f:
        all_repos = json.load(f)

    labels_path = os.path.join("c3", "data", "to_label.csv")
    labels = {}
    with open(labels_path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            qid = row["query_id"]
            rel_str = row.get("relevance", "").strip()
            labels.setdefault(qid, {})[row["full_name"]] = int(rel_str) if rel_str else 0

    rounds_to_test = [1, 2]
    # variant keys: "Baseline", "GNN(R=1)", "GNN(R=2)"
    variant_keys = ["Baseline"] + [f"GNN(R={r})" for r in rounds_to_test]

    totals = {v: {m: 0.0 for m in METRIC_NAMES} for v in variant_keys}
    per_query = []
    num_queries = 0

    for qi, qid in enumerate(sorted(all_repos.keys())):
        query_text = all_repos[qid]["query"]
        repos = all_repos[qid]["repos"]
        query_labels = labels.get(qid, {})

        if not repos:
            continue

        num_queries += 1
        print(f"[{qi+1}/{len(all_repos)}] {qid}: \"{query_text[:60]}\"")

        # Build base embeddings (same text construction as rank_hybrid)
        base_embeddings = np.array([
            embed_text("search_document: " + repo_text(r)) for r in repos
        ])

        query_row = {"query_id": qid, "query": query_text}

        # --- Baseline ---
        names_base, _ = rank_hybrid(query_text, repos,
                                    doc_embeddings=base_embeddings.tolist())
        m_base = compute_metrics(names_base, query_labels)
        query_row["Baseline"] = m_base
        for m in METRIC_NAMES:
            totals["Baseline"][m] += m_base[m]

        # --- GNN variants ---
        adj = build_adjacency(base_embeddings)
        for r in rounds_to_test:
            key = f"GNN(R={r})"
            enriched = gcn_enrich(base_embeddings, adj, rounds=r)
            names_gnn, _ = rank_hybrid(query_text, repos,
                                       doc_embeddings=enriched.tolist())
            m_gnn = compute_metrics(names_gnn, query_labels)
            query_row[key] = m_gnn
            for m in METRIC_NAMES:
                totals[key][m] += m_gnn[m]

        per_query.append(query_row)

        # Print per-query comparison
        for v in variant_keys:
            vals = query_row[v]
            print(f"  {v:<12}  P@5={vals['P@5']:.4f}  R@10={vals['R@10']:.4f}  "
                  f"MRR={vals['MRR']:.4f}  nDCG@10={vals['nDCG@10']:.4f}  "
                  f"P@5s={vals['P@5(strict)']:.4f}")
        print()

    # --- Averages ---
    print("=" * 78)
    print("AVERAGES\n")
    header = f"{'Variant':<12}  {'P@5':>6}  {'R@10':>6}  {'MRR':>6}  {'nDCG@10':>8}  {'P@5(s)':>7}"
    print(header)
    print("-" * len(header))

    averages = {}
    for v in variant_keys:
        avg = {m: totals[v][m] / num_queries for m in METRIC_NAMES}
        averages[v] = avg
        print(f"{v:<12}  {avg['P@5']:>6.4f}  {avg['R@10']:>6.4f}  "
              f"{avg['MRR']:>6.4f}  {avg['nDCG@10']:>8.4f}  {avg['P@5(strict)']:>7.4f}")

    # --- Save ---
    output = {"num_queries": num_queries, "averages": averages, "per_query": per_query}
    out_path = os.path.join("c3", "data", "gnn_eval_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
