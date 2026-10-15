"""
test_connection.py — Verify that we can reach the Neo4j Aura knowledge graph.

Loads NEO4J_URI, NEO4J_USERNAME, and NEO4J_PASSWORD from the project's .env file,
opens a session, runs two quick Cypher queries, and prints the results.
"""

import sys
from dotenv import load_dotenv
import os
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError

# ── 1. Load credentials from .env ──────────────────────────────────────────────
load_dotenv()  # reads the .env file at the project root

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

# Quick sanity check: make sure all three variables are present
if not all([NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD]):
    print("❌ One or more NEO4J_ environment variables are missing from .env.")
    print("   Expected: NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD")
    sys.exit(1)

# ── 2. Connect and query ───────────────────────────────────────────────────────
try:
    # Create a driver instance (neo4j+s:// URIs are handled automatically)
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

    # Verify connectivity before running queries
    driver.verify_connectivity()
    print(f"✅ Connected to Neo4j at {NEO4J_URI}\n")

    with driver.session() as session:
        # --- Query 1: total node count ---
        result = session.run("MATCH (n) RETURN count(n) AS nodes")
        total_nodes = result.single()["nodes"]
        print(f"📊 Total nodes in the graph: {total_nodes}\n")

        # --- Query 2: per-label breakdown ---
        result = session.run(
            "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS c ORDER BY c DESC"
        )
        records = list(result)

        print("🏷️  Per-label breakdown:")
        print(f"   {'Label':<25} {'Count':>5}")
        print(f"   {'─' * 25} {'─' * 5}")
        for record in records:
            print(f"   {record['label']:<25} {record['c']:>5}")

    # ── 3. Clean up ────────────────────────────────────────────────────────────
    driver.close()
    print("\n🔒 Driver closed. All good!")

except AuthError:
    print("❌ Authentication failed — double-check NEO4J_USERNAME and NEO4J_PASSWORD in .env.")
    sys.exit(1)

except ServiceUnavailable:
    print("❌ Could not reach the Neo4j instance.")
    print("   • Is the URI correct?  (current: {})".format(NEO4J_URI))
    print("   • If using Aura Free, the instance may be paused — resume it in the Aura console.")
    sys.exit(1)

except Exception as e:
    # Catch-all for anything unexpected, but still keep it friendly
    print(f"❌ Unexpected error: {e}")
    sys.exit(1)
