"""
graph_expand.py — Use the graph's structure to run a smarter second GitHub search.

Reads the graph built by graph_builder, finds the most-connected repos,
extracts their dominant topics, searches GitHub for those topics, and
returns NEW repos not already in the graph.

Usage:  python -m graphsearch.graph_expand
Needs:  Neo4j running, Ollama running, internet for GitHub API,
        .env with NEO4J_* and GITHUB_TOKEN.
"""

import json
import os
import sys
from collections import Counter

from dotenv import load_dotenv
from neo4j import GraphDatabase

# Make project root importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from c3.github_client import search_repositories
from graphsearch.graph_builder import build_graph


def expand_via_graph(top_k_anchors=5, top_topics=3, max_new=10) -> list:
    """
    Read the current Neo4j graph, find its most-connected repos,
    extract dominant topics, search GitHub with those topics, and
    return up to max_new NEW repos not already in the graph.
    """

    # --- connect to Neo4j ---
    load_dotenv()
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USERNAME")
    pw = os.getenv("NEO4J_PASSWORD")
    driver = GraphDatabase.driver(uri, auth=(user, pw))

    try:
        with driver.session() as session:

            # 1. Get every repo's full_name, topics, and degree (total relationships)
            result = session.run(
                """
                MATCH (r:Repo)
                OPTIONAL MATCH (r)-[rel]-()
                RETURN r.full_name AS name,
                       r.topics    AS topics,
                       count(rel)  AS degree
                ORDER BY degree DESC
                """
            )
            rows = [dict(record) for record in result]

    finally:
        driver.close()

    if not rows:
        print("Graph is empty — nothing to expand.")
        return []

    # Collect all names already in the graph for deduplication later
    existing_names = {row["name"] for row in rows}

    # 2. Pick the top-k most-connected repos (the "anchors")
    anchors = rows[:top_k_anchors]
    print("Anchor repos (most connected):")
    for a in anchors:
        print(f"  {a['name']}  (degree {a['degree']})")

    # 3. Count topics across those anchors, pick the most common ones
    topic_counter = Counter()
    for a in anchors:
        for t in (a["topics"] or []):
            if t:  # skip empty strings
                topic_counter[t] += 1

    themes = [t for t, _ in topic_counter.most_common(top_topics)]
    print(f"\nTop themes: {themes}")

    if not themes:
        print("No topics found on anchor repos — can't expand.")
        return []

    # 4. Build a search query from those topics and hit GitHub
    search_query = " ".join(themes)
    print(f"New GitHub search: \"{search_query}\"\n")

    candidates = search_repositories(search_query, max_results=max_new + len(existing_names))

    # 5. Drop any repo already in the graph, keep up to max_new
    new_repos = []
    for repo in candidates:
        if repo["full_name"] not in existing_names:
            new_repos.append(repo)
            if len(new_repos) >= max_new:
                break

    # Print what we found
    print(f"New repos found: {len(new_repos)}")
    for r in new_repos:
        print(f"  {r['full_name']}  ⭐ {r['stars']}")

    return new_repos


# ---------------------------------------------------------------------------
# Quick test: build graph for q1, then expand it
# ---------------------------------------------------------------------------

def main():
    data_path = os.path.join(os.path.dirname(__file__), "..", "c3", "data", "repos.json")
    with open(data_path, encoding="utf-8") as f:
        data = json.load(f)

    q1 = data["q1"]
    print(f'=== Building graph for: "{q1["query"]}" ===\n')
    build_graph(q1["query"], q1["repos"])

    print("\n=== Expanding via graph ===\n")
    new_repos = expand_via_graph()
    print(f"\nTotal new repos: {len(new_repos)}")


if __name__ == "__main__":
    main()
