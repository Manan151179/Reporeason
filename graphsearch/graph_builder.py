"""
graph_builder.py — Build a fresh Neo4j graph of repos for a single search.

Usage:  python -m graphsearch.graph_builder
Needs:  Neo4j running, Ollama running (with nomic-embed-text pulled),
        .env with NEO4J_URI / NEO4J_USERNAME / NEO4J_PASSWORD.
"""

import json
import os
import sys

from dotenv import load_dotenv
from neo4j import GraphDatabase

# Reuse the project's own embedding helpers
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from c3.embeddings import embed_text, cosine_similarity


# ---------------------------------------------------------------------------
# Core function — call this from anywhere with a query + list of repo dicts
# ---------------------------------------------------------------------------

def build_graph(query: str, repos: list) -> dict:
    """
    Clear Neo4j, embed every repo, create :Repo nodes and
    SHARES_TOPIC / SIMILAR_TO edges.  Returns a summary dict.
    """

    # --- connect to Neo4j using .env creds ---
    load_dotenv()
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USERNAME")
    pw = os.getenv("NEO4J_PASSWORD")
    driver = GraphDatabase.driver(uri, auth=(user, pw))

    try:
        with driver.session() as session:

            # 1. Wipe the graph — fresh build every search
            print("[1/4] Clearing existing graph …")
            session.run("MATCH (n) DETACH DELETE n")

            # 2. Embed each repo and collect vectors
            print(f"[2/4] Embedding {len(repos)} repos …")
            vectors = []  # parallel list — vectors[i] belongs to repos[i]
            for i, repo in enumerate(repos):
                name = repo.get("full_name") or ""
                desc = repo.get("description") or ""
                topics = repo.get("topics") or []
                text = f"{name} {desc} {' '.join(topics)}".strip()

                # nomic-embed-text expects a task prefix for documents
                vec = embed_text("search_document: " + text)
                vectors.append(vec)
                print(f"  embedded {i + 1}/{len(repos)}: {name}")

            # 3. Create one :Repo node per repo (store embedding for later reuse)
            print("[3/4] Creating Repo nodes …")
            for repo, vec in zip(repos, vectors):
                # Accept both html_url and url — whichever the dict has
                url = repo.get("url") or repo.get("html_url") or ""
                session.run(
                    """
                    CREATE (r:Repo {
                        full_name:   $full_name,
                        url:         $url,
                        description: $description,
                        topics:      $topics,
                        language:    $language,
                        stars:       $stars,
                        pushed_at:   $pushed_at,
                        embedding:   $embedding
                    })
                    """,
                    full_name=repo.get("full_name") or "",
                    url=url,
                    description=repo.get("description") or "",
                    topics=repo.get("topics") or [],
                    language=repo.get("language") or "",
                    stars=repo.get("stars", 0),
                    pushed_at=repo.get("pushed_at") or "",
                    embedding=vec,
                )

            # 4. Create edges (only a < b to avoid duplicates)
            print("[4/4] Creating edges …")
            topic_count = 0
            similar_count = 0

            # Pre-compute topic sets for SHARES_TOPIC
            topic_sets = [set(r.get("topics") or []) for r in repos]

            # --- SHARES_TOPIC: any pair sharing >= 1 topic ---
            for i in range(len(repos)):
                for j in range(i + 1, len(repos)):
                    shared = sorted(topic_sets[i] & topic_sets[j])
                    if shared:
                        session.run(
                            """
                            MATCH (a:Repo {full_name: $a}),
                                  (b:Repo {full_name: $b})
                            CREATE (a)-[:SHARES_TOPIC {shared: $shared, count: $count}]->(b)
                            """,
                            a=repos[i]["full_name"],
                            b=repos[j]["full_name"],
                            shared=shared,
                            count=len(shared),
                        )
                        topic_count += 1

            # --- SIMILAR_TO: cosine >= 0.60, top-5 neighbours per repo ---
            # Collect all qualifying pairs first, then prune to top-5 per repo
            # ponytail: O(n²) scan — fine for ≤hundreds of repos
            pairs = []  # (i, j, score)
            for i in range(len(repos)):
                for j in range(i + 1, len(repos)):
                    score = round(cosine_similarity(vectors[i], vectors[j]), 3)
                    if score >= 0.60:
                        pairs.append((i, j, score))

            # For each repo keep at most 5 highest-scoring neighbours
            from collections import defaultdict
            neighbour_counts = defaultdict(int)

            # Sort pairs descending by score so we pick the best first
            pairs.sort(key=lambda p: p[2], reverse=True)

            for i, j, score in pairs:
                if neighbour_counts[i] >= 5 or neighbour_counts[j] >= 5:
                    continue
                session.run(
                    """
                    MATCH (a:Repo {full_name: $a}),
                          (b:Repo {full_name: $b})
                    CREATE (a)-[:SIMILAR_TO {score: $score}]->(b)
                    """,
                    a=repos[i]["full_name"],
                    b=repos[j]["full_name"],
                    score=score,
                )
                neighbour_counts[i] += 1
                neighbour_counts[j] += 1
                similar_count += 1

    finally:
        driver.close()

    summary = {
        "repos": len(repos),
        "shares_topic": topic_count,
        "similar_to": similar_count,
    }
    print(f"\nDone — {summary}")
    return summary


# ---------------------------------------------------------------------------
# Quick test: load q1 from repos.json and build its graph
# ---------------------------------------------------------------------------

def main():
    data_path = os.path.join(os.path.dirname(__file__), "..", "c3", "data", "repos.json")
    with open(data_path, encoding="utf-8") as f:
        data = json.load(f)

    q1 = data["q1"]
    print(f'Query: "{q1["query"]}"')
    print(f"Repos: {len(q1['repos'])}\n")

    summary = build_graph(q1["query"], q1["repos"])
    print(f"\nSummary: {summary}")


if __name__ == "__main__":
    main()
