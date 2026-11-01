"""
graph_rank.py — Full graph search pipeline: build → expand → re-rank.

The graph is used to FIND more repos (expand step). The final ranking is
purely the hybrid score — each repo judged on its own merits.

Usage:  python -m graphsearch.graph_rank
Needs:  Neo4j running, Ollama running, internet for GitHub API,
        .env with NEO4J_* and GITHUB_TOKEN.
"""

import json
import os
import sys

# Make project root importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from graphsearch.graph_builder import build_graph
from graphsearch.graph_expand import expand_via_graph
from c3.rankers import rank_detailed
from graphsearch.communities import (
    build_community_graph, detect_communities, community_aware_rerank,
)


def graph_search(query, initial_repos, community_aware=True) -> list:
    """
    Full graph search pipeline:
      1. Build graph on initial repos
      2. Expand (graph-driven GitHub search for new repos)
      3. Merge & dedupe
      4. Rebuild graph on full pool
      5. Rank by hybrid score (graph used only to find, not to rank)
    Returns a list of result dicts sorted best-first.
    """

    # Track which repos came from the expansion step
    initial_names = {r["full_name"] for r in initial_repos}

    # 1. Build initial graph
    print("=== Step 1: Build initial graph ===\n")
    build_graph(query, initial_repos)

    # 2. Expand — find new repos via the graph's structure
    print("\n=== Step 2: Expand via graph ===\n")
    new_repos = expand_via_graph()

    # 3. Merge initial + new, deduplicated by full_name
    print("\n=== Step 3: Merge & dedupe ===\n")
    seen = set()
    full_pool = []
    for r in initial_repos + new_repos:
        if r["full_name"] not in seen:
            seen.add(r["full_name"])
            full_pool.append(r)
    print(f"Full pool: {len(full_pool)} repos ({len(full_pool) - len(initial_names)} new)")

    # 4. Rebuild graph on the full pool so new repos get edges too
    print("\n=== Step 4: Rebuild graph on full pool ===\n")
    build_graph(query, full_pool)

    # 5. Hybrid score from rank_detailed — this IS the final score
    print("\n=== Step 5: Hybrid scoring (= final ranking) ===\n")
    detailed = rank_detailed(query, full_pool)

    # Build result list sorted by hybrid score (rank_detailed already sorts)
    # Each item carries FULL repo fields + fit_score + is_new
    results = []
    for d in detailed:
        repo = d["repo"]
        name = repo["full_name"]
        results.append({
            "full_name": name,
            "url": repo.get("url") or repo.get("html_url") or "",
            "description": repo.get("description") or "",
            "topics": repo.get("topics") or [],
            "language": repo.get("language") or "",
            "stars": repo.get("stars", 0),
            "pushed_at": repo.get("pushed_at") or "",
            "fit_score": round(d["score"], 4),
            "is_new": name not in initial_names,
        })

    # 6. Community-aware reranking (optional)
    if community_aware:
        print("\n=== Step 6: Community-aware reranking ===\n")
        # Reuse embeddings from rank_detailed's cache via the same doc texts
        from c3.embeddings import embed_text
        from c3.rankers import repo_text
        embeddings = [
            embed_text("search_document: " + repo_text(r))
            for r in full_pool
        ]
        G = build_community_graph(full_pool, embeddings)
        _, node_comm = detect_communities(G)

        # Map result names -> pool indices for reranking
        name_to_idx = {r["full_name"]: i for i, r in enumerate(full_pool)}
        ranked_indices = [name_to_idx[r["full_name"]] for r in results]
        reranked_indices = community_aware_rerank(ranked_indices, node_comm)

        # Reorder results and attach community_id
        idx_to_result = {name_to_idx[r["full_name"]]: r for r in results}
        results = [idx_to_result[i] for i in reranked_indices]
        for r in results:
            r["community_id"] = node_comm[name_to_idx[r["full_name"]]]
    else:
        for r in results:
            r["community_id"] = None

    # Print top 15 as a table
    print("=== Final Ranking (top 15) ===\n")
    print(f"{'#':<3} {'Repo':<55} {'Stars':>6} {'Hybrid':>7} {'C':>2}  {'New?'}")
    print("-" * 82)
    for i, r in enumerate(results[:15], 1):
        tag = " *" if r["is_new"] else ""
        cid = r["community_id"] if r["community_id"] is not None else "-"
        print(
            f"{i:<3} {r['full_name']:<55} {r['stars']:>6} "
            f"{r['fit_score']:>7.4f} {cid:>2}{tag}"
        )

    return results


# ---------------------------------------------------------------------------
# Quick test: load q1, run the full pipeline
# ---------------------------------------------------------------------------

def main():
    data_path = os.path.join(os.path.dirname(__file__), "..", "c3", "data", "repos.json")
    with open(data_path, encoding="utf-8") as f:
        data = json.load(f)

    q1 = data["q1"]
    print(f'Query: "{q1["query"]}"\n')

    results = graph_search(q1["query"], q1["repos"])
    print(f"\nTotal ranked: {len(results)}")


if __name__ == "__main__":
    main()
