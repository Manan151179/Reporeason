"""
communities.py — Community detection over the repo-similarity graph.

Builds the same edges as graph_builder (SIMILAR_TO + SHARES_TOPIC) in a
pure-networkx Graph, detects communities (Leiden → Louvain fallback),
and exposes a diversity-aware reranker.

Usage:  python -m graphsearch.communities
"""

import json
import os
import sys
from collections import defaultdict

import networkx as nx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from c3.embeddings import embed_text, cosine_similarity


# ---------------------------------------------------------------------------
# 1. Build graph  (mirrors graph_builder edges exactly)
# ---------------------------------------------------------------------------

def build_community_graph(repos, embeddings):
    """
    Return an undirected networkx.Graph whose nodes are repo indices
    with SIMILAR_TO and SHARES_TOPIC edges exactly as graph_builder defines.
    """
    n = len(repos)
    G = nx.Graph()
    G.add_nodes_from(range(n))

    # --- SHARES_TOPIC: any pair sharing >= 1 topic ---
    topic_sets = [set(r.get("topics") or []) for r in repos]
    for i in range(n):
        for j in range(i + 1, n):
            shared = topic_sets[i] & topic_sets[j]
            if shared:
                G.add_edge(i, j, type="SHARES_TOPIC", count=len(shared))

    # --- SIMILAR_TO: cosine >= 0.60, top-5 neighbours per repo ---
    # ponytail: O(n²) scan — same as graph_builder, fine for ≤hundreds
    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            score = round(cosine_similarity(embeddings[i], embeddings[j]), 3)
            if score >= 0.60:
                pairs.append((i, j, score))

    pairs.sort(key=lambda p: p[2], reverse=True)
    counts = defaultdict(int)
    for i, j, score in pairs:
        if counts[i] >= 5 or counts[j] >= 5:
            continue
        G.add_edge(i, j, type="SIMILAR_TO", score=score)
        counts[i] += 1
        counts[j] += 1

    return G


# ---------------------------------------------------------------------------
# 2. Community detection  (Leiden → Louvain fallback)
# ---------------------------------------------------------------------------

def detect_communities(G):
    """
    Returns (list_of_sets, node_to_community_dict).
    Tries Leiden (leidenalg + igraph); falls back to networkx Louvain.
    Isolated nodes become their own community.
    """
    try:
        import igraph as ig
        import leidenalg

        # Convert networkx → igraph
        mapping = {node: idx for idx, node in enumerate(G.nodes())}
        ig_G = ig.Graph(n=len(mapping), edges=[
            (mapping[u], mapping[v]) for u, v in G.edges()
        ], directed=False)

        partition = leidenalg.find_partition(ig_G, leidenalg.ModularityVertexPartition)

        reverse_map = {idx: node for node, idx in mapping.items()}
        communities = [set() for _ in range(len(partition))]
        node_to_comm = {}
        for comm_id, members in enumerate(partition):
            for idx in members:
                node = reverse_map[idx]
                communities[comm_id].add(node)
                node_to_comm[node] = comm_id

    except ImportError:
        # Louvain fallback with fixed seed
        comm_list = nx.community.louvain_communities(G, seed=42)
        communities = [set(c) for c in comm_list]
        node_to_comm = {}
        for comm_id, members in enumerate(communities):
            for node in members:
                node_to_comm[node] = comm_id

    # Ensure isolated nodes get their own community
    for node in G.nodes():
        if node not in node_to_comm:
            new_id = len(communities)
            communities.append({node})
            node_to_comm[node] = new_id

    return communities, node_to_comm


# ---------------------------------------------------------------------------
# 3. Diversity-aware reranking
# ---------------------------------------------------------------------------

def community_aware_rerank(order, node_community, top_n=10):
    """
    Round-robin community diversity within the top_n head only.
    Items beyond top_n keep their original hybrid order.
    """
    head = order[:top_n]
    tail = order[top_n:]

    result = []
    seen_communities = set()
    remaining = []

    for node in head:
        comm = node_community.get(node)
        if comm not in seen_communities:
            seen_communities.add(comm)
            result.append(node)
        else:
            remaining.append(node)

    result.extend(remaining)
    result.extend(tail)
    return result


def diversity_at_k(order, node_community, k=5):
    """Number of distinct communities in the top-k of *order*."""
    return len({node_community[n] for n in order[:k] if n in node_community})


# ---------------------------------------------------------------------------
# 4. Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    data_path = os.path.join(os.path.dirname(__file__), "..", "c3", "data", "repos.json")
    with open(data_path, encoding="utf-8") as f:
        data = json.load(f)

    q1 = data["q1"]
    repos = q1["repos"]
    print(f'Query: "{q1["query"]}"')
    print(f"Repos: {len(repos)}\n")

    # Embed with the same prefix graph_builder uses
    print("Embedding repos …")
    embeddings = []
    for i, repo in enumerate(repos):
        name = repo.get("full_name") or ""
        desc = repo.get("description") or ""
        topics = repo.get("topics") or []
        text = f"{name} {desc} {' '.join(topics)}".strip()
        embeddings.append(embed_text("search_document: " + text))
        print(f"  {i + 1}/{len(repos)}: {name}")

    print("\nBuilding community graph …")
    G = build_community_graph(repos, embeddings)

    communities, node_comm = detect_communities(G)

    print(f"\n{'='*60}")
    print(f"Communities: {len(communities)}")
    print(f"Nodes: {G.number_of_nodes()}  Edges: {G.number_of_edges()}")
    print(f"Avg degree: {sum(d for _, d in G.degree()) / max(G.number_of_nodes(), 1):.2f}")
    print(f"{'='*60}\n")

    for cid, members in enumerate(communities):
        names = [repos[m].get("full_name", "?") for m in sorted(members)]
        print(f"Community {cid} ({len(members)} repos):")
        for n in names:
            print(f"  • {n}")
        print()

    # --- Write community_q1.json ---
    graph_json = {
        "nodes": [
            {"index": i, "name": repos[i].get("full_name", "?"), "community": node_comm[i]}
            for i in range(len(repos))
        ],
        "edges": [[u, v] for u, v in G.edges()],
    }
    out_path = os.path.join(os.path.dirname(__file__), "community_q1.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(graph_json, f, indent=2)
    print(f"Saved graph -> {out_path}")
