"""
run_community_eval.py — 3-way ablation: Traditional RAG vs GraphRAG vs Community-aware.

Usage:  python -m c3.run_community_eval
"""

import sys
import os
import json
import csv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from c3.rankers import rank_dense, rank_hybrid
from c3.metrics import precision_at_k, ndcg_at_k
from c3.embeddings import embed_text
from graphsearch.communities import (
    build_community_graph, detect_communities,
    community_aware_rerank, diversity_at_k,
)


def main():
    # --- Load repos and labels (same paths as run_all) ---
    repos_path = os.path.join("c3", "data", "repos.json")
    with open(repos_path, "r", encoding="utf-8") as f:
        all_queries = json.load(f)

    labels_path = os.path.join("c3", "data", "to_label.csv")
    labels = {}
    with open(labels_path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            qid = row["query_id"]
            rel_str = row.get("relevance", "").strip()
            labels.setdefault(qid, {})[row["full_name"]] = int(rel_str) if rel_str else 0

    print(f"Loaded {len(all_queries)} queries, labels for {len(labels)} queries\n")

    # --- Define the three variants ---
    variants = ["RAG", "GraphRAG", "Community"]
    metric_names = ["nDCG@10", "P@5", "div@5"]

    totals = {v: {m: 0.0 for m in metric_names} for v in variants}
    per_query = []
    num_queries = 0

    for qi, qid in enumerate(sorted(all_queries.keys())):
        entry = all_queries[qid]
        query = entry["query"]
        repos = entry["repos"]
        query_labels = labels.get(qid, {})

        print(f"[{qi+1}/{len(all_queries)}] {qid}: \"{query[:60]}\"")

        if not repos:
            print("  (no repos, skipping)\n")
            continue

        num_queries += 1

        # --- Embed once, reuse everywhere ---
        name_to_idx = {r["full_name"]: i for i, r in enumerate(repos)}
        embeddings = []
        for repo in repos:
            name = repo.get("full_name") or ""
            desc = repo.get("description") or ""
            topics = repo.get("topics") or []
            text = f"{name} {desc} {' '.join(topics)}".strip()
            embeddings.append(embed_text("search_document: " + text))

        # --- Build community graph and detect communities ---
        G = build_community_graph(repos, embeddings)
        _, node_comm = detect_communities(G)

        # --- Three orderings (all return full_name lists) ---
        rag_names = rank_dense(query, repos)
        graphrag_names, _ = rank_hybrid(query, repos, doc_embeddings=embeddings)
        # Convert GraphRAG names → indices → rerank → back to names
        graphrag_indices = [name_to_idx[n] for n in graphrag_names]
        community_indices = community_aware_rerank(graphrag_indices, node_comm)
        community_names = [repos[i]["full_name"] for i in community_indices]

        orderings = {
            "RAG":       rag_names,
            "GraphRAG":  graphrag_names,
            "Community": community_names,
        }

        row = {"query_id": qid, "query": query}
        for v in variants:
            ranked = orderings[v]
            n10 = ndcg_at_k(ranked, query_labels, k=10)
            p5  = precision_at_k(ranked, query_labels, k=5)
            # diversity: map names back to indices for node_comm lookup
            idx_order = [name_to_idx[n] for n in ranked]
            d5  = diversity_at_k(idx_order, node_comm, k=5)

            totals[v]["nDCG@10"] += n10
            totals[v]["P@5"]     += p5
            totals[v]["div@5"]   += d5

            row[v] = {"nDCG@10": round(n10, 4), "P@5": round(p5, 4), "div@5": d5}
            print(f"  {v:<11}  nDCG@10={n10:.4f}  P@5={p5:.4f}  div@5={d5}")

        per_query.append(row)
        print()

    # --- Averages ---
    print("=" * 64)
    print("AVERAGES:\n")
    header = f"{'Variant':<12} {'nDCG@10':>8} {'P@5':>6} {'div@5':>6}"
    print(header)
    print("-" * len(header))

    averages = {}
    for v in variants:
        avg = {m: round(totals[v][m] / num_queries, 4) for m in metric_names}
        averages[v] = avg
        print(f"{v:<12} {avg['nDCG@10']:>8.4f} {avg['P@5']:>6.4f} {avg['div@5']:>6.1f}")

    # --- Save ---
    output = {"num_queries": num_queries, "averages": averages, "per_query": per_query}
    out_path = os.path.join("c3", "data", "community_eval.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
