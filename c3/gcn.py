# Import sys and os so we can add the project root to the import path
import sys
import os

# Add the project root to sys.path so imports work from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import numpy as np
from c3.embeddings import embed_text, cosine_similarity
from c3.rankers import repo_text


def build_adjacency(embeddings, sim_threshold=0.60, top_k=5):
    """
    Build an undirected adjacency list matching graph_builder.py's
    SIMILAR_TO logic: cosine >= sim_threshold, each node keeps at most
    top_k neighbors, edges are undirected (j in adj[i] iff i in adj[j]).
    """
    n = len(embeddings)
    # Pre-compute norms for fast cosine
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    safe_norms = np.where(norms == 0, 1.0, norms)
    normed = embeddings / safe_norms
    sim_matrix = normed @ normed.T

    # Collect qualifying pairs (i < j), sorted by score descending
    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            s = sim_matrix[i, j]
            if s >= sim_threshold:
                pairs.append((i, j, float(s)))
    pairs.sort(key=lambda p: p[2], reverse=True)

    # Cap each node at top_k neighbors (same joint-cap as graph_builder)
    adjacency = {i: set() for i in range(n)}
    counts = [0] * n
    for i, j, _ in pairs:
        if counts[i] >= top_k or counts[j] >= top_k:
            continue
        adjacency[i].add(j)
        adjacency[j].add(i)
        counts[i] += 1
        counts[j] += 1
    return adjacency


def gcn_enrich(embeddings, adjacency, rounds=1):
    """
    One-layer GCN-style enrichment (no learned weights).
    Each round: new[i] = mean(embeddings[i] + neighbors), then L2-normalize.
    A node with no neighbors keeps itself (then normalized).
    """
    out = embeddings.copy()
    for _ in range(rounds):
        new = np.empty_like(out)
        for i in range(len(out)):
            neighbors = adjacency.get(i, set())
            # Self-loop: include the node itself
            indices = [i] + list(neighbors)
            new[i] = out[indices].mean(axis=0)
        # L2-normalize each vector
        norms = np.linalg.norm(new, axis=1, keepdims=True)
        safe_norms = np.where(norms == 0, 1.0, norms)
        out = new / safe_norms
    return out


if __name__ == "__main__":

    # Load repo data, take query q1
    repos_path = os.path.join("c3", "data", "repos.json")
    with open(repos_path, "r", encoding="utf-8") as f:
        all_repos = json.load(f)

    qid = "q1"
    query_text = all_repos[qid]["query"]
    repos = all_repos[qid]["repos"]
    n = len(repos)

    print(f'Query [{qid}]: "{query_text}"')
    print(f"Repos: {n}\n")

    # Embed query (same prefix as rank_hybrid)
    query_vec = np.array(embed_text("search_query: " + query_text))

    # Embed each repo (same text construction + prefix as rank_hybrid)
    print("Embedding repos …")
    raw_embeddings = []
    for repo in repos:
        doc_text = "search_document: " + repo_text(repo)
        raw_embeddings.append(embed_text(doc_text))
    embeddings = np.array(raw_embeddings)

    # Cosine to query BEFORE enrichment
    before = []
    for i in range(n):
        before.append(cosine_similarity(query_vec.tolist(), embeddings[i].tolist()))

    # Build adjacency and enrich
    adj = build_adjacency(embeddings)
    enriched = gcn_enrich(embeddings, adj, rounds=1)

    # Cosine to query AFTER enrichment
    after = []
    for i in range(n):
        after.append(cosine_similarity(query_vec.tolist(), enriched[i].tolist()))

    # Average degree
    degrees = [len(adj[i]) for i in range(n)]
    avg_degree = sum(degrees) / n if n else 0

    # Build table sorted by biggest rise (delta descending)
    table = []
    for i in range(n):
        table.append({
            "name": repos[i]["full_name"],
            "stars": repos[i].get("stars", 0),
            "before": before[i],
            "after": after[i],
            "delta": after[i] - before[i],
        })
    table.sort(key=lambda x: x["delta"], reverse=True)

    # Print
    print(f"\nAvg node degree: {avg_degree:.2f}\n")
    header = f"{'Repo':<65} {'Stars':>6} {'Before':>7} {'After':>7} {'Delta':>7}"
    print(header)
    print("-" * len(header))
    for row in table:
        print(f"{row['name']:<65} {row['stars']:>6} {row['before']:>7.4f} {row['after']:>7.4f} {row['delta']:>+7.4f}")
