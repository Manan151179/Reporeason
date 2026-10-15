"""
graphrag.py — Simple GraphRAG pipeline for the RepoReason knowledge graph.

Pipeline:  question → keyword extraction → Neo4j retrieval (2-hop) → evidence → LLM → answer

Uses the exact schema from reporeason_kg.cypher:
  Labels: ProjectQuery, Repository, RelevanceLabel, Language, License,
          Signal, RankingMethod, Metric, Paper, Technique
  Relationships: HAS_CANDIDATE, LABELED_AS, WRITTEN_IN, HAS_LICENSE,
                 USES_SIGNAL, SCORED, IMPLEMENTS, BUILDS_ON, INTRODUCES,
                 DEFINES, GROUNDED_IN
"""

import sys
import os
from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError

try:
    import ollama
except ImportError:
    print("❌ The 'ollama' package is not installed. Run:  pip install ollama")
    sys.exit(1)

# ── Load Neo4j credentials from .env ───────────────────────────────────────────
load_dotenv()
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

if not all([NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD]):
    print("❌ Missing NEO4J_URI / NEO4J_USERNAME / NEO4J_PASSWORD in .env")
    sys.exit(1)

# ── Stop-words to ignore when extracting keywords ─────────────────────────────
STOP_WORDS = {
    "a", "an", "the", "and", "or", "is", "are", "was", "were", "it", "its",
    "in", "on", "at", "to", "for", "of", "with", "by", "from", "as", "that",
    "this", "which", "what", "how", "who", "where", "when", "do", "does",
    "did", "be", "been", "being", "have", "has", "had", "not", "but", "if",
    "so", "than", "can", "could", "will", "would", "should", "may", "about",
    "up", "out", "then", "them", "they", "their", "there", "some", "all",
    "any", "most", "also", "very", "just", "into", "over", "such",
}

# ── Text-like properties to search for keyword matches ────────────────────────
# These are the properties across all node types that contain useful text.
SEARCHABLE_PROPS = [
    "name", "full_name", "description", "meaning", "title",
    "query", "spdx_id", "label",
]

# ── Hub-node threshold ────────────────────────────────────────────────────────
# Nodes with more than this many relationships are considered "hubs" and are
# NOT expanded during the 2-hop phase to prevent flooding (e.g. RelevanceLabel
# nodes connect to 18+ repositories and drown out useful facts).
HUB_DEGREE_THRESHOLD = 6

# ── Maximum number of facts to pass to the LLM ───────────────────────────────
MAX_FACTS = 25


# =============================================================================
# HELPER — get a human-readable display name for any node
# =============================================================================
def node_display_name(props):
    """
    Return the first non-empty value from a priority list of property keys.
    This fixes Problem 3: nodes like RelevanceLabel that have no 'name'
    were showing as '' — now we fall back through several keys.

    Extra: if none of the priority keys match, we build a compact dict
    string as a last resort.  But if that string looks like a raw dict
    (e.g. "{'spdx_id': 'MIT'}"), we try to pull out the spdx_id value
    so License nodes display 'MIT' instead of the ugly dict text.
    """
    for key in ("name", "title", "text", "full_name", "label", "id"):
        val = props.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()

    # Before falling back to the raw dict string, check if the node
    # has a recognisable key like spdx_id that we can show instead.
    if props.get("spdx_id"):
        return str(props["spdx_id"]).strip()

    # True last resort: compact dict of all properties
    return str(dict(props)) if props else "(unknown)"


# =============================================================================
# 1. RETRIEVE — entity-focused keyword search + smart 2-hop expansion
# =============================================================================
def extract_keywords(question):
    """Pull lowercase keywords from the question, dropping stop-words and short tokens."""
    words = []
    for word in question.lower().split():
        # Strip punctuation from edges
        cleaned = word.strip("?.,!;:'\"\u00a0()[]{}—-")
        if cleaned and cleaned not in STOP_WORDS and len(cleaned) > 1:
            words.append(cleaned)
    return list(dict.fromkeys(words))  # deduplicate, preserve order


def retrieve(question, driver):
    """
    Entity-focused retrieval that avoids hub-node flooding.

    Steps:
      A. Find seed nodes whose text properties match any keyword.
      B. Collect ALL 1-hop relationships of every seed node (both directions).
      C. Add 2-hop facts ONLY along paths that connect back toward another
         seed-related node, skipping expansion through hub nodes (degree > 6).
      D. Order: seed-touching facts first, then 2-hop facts.  Cap at ~25.

    Returns (facts_list, seed_summaries_list).
    """
    keywords = extract_keywords(question)
    if not keywords:
        return [], []

    # --- Step A: Find seed nodes matching any keyword ---
    # Build a Cypher WHERE clause that checks every searchable property
    # against every keyword using toLower + CONTAINS.
    conditions = []
    params = {}
    for i, kw in enumerate(keywords):
        param_name = f"kw{i}"
        params[param_name] = kw
        for prop in SEARCHABLE_PROPS:
            conditions.append(
                f"toLower(coalesce(n.{prop}, '')) CONTAINS ${param_name}"
            )

    where_clause = " OR ".join(conditions)

    seed_query = f"""
        MATCH (n)
        WHERE {where_clause}
        RETURN n, labels(n)[0] AS lbl, elementId(n) AS eid
    """

    seed_nodes = []       # list of (elementId, label, props_dict)
    seed_ids = set()      # element IDs for fast membership checks
    seed_summaries = []   # human-readable summaries of seed nodes

    with driver.session() as session:
        result = session.run(seed_query, **params)
        for record in result:
            node = record["n"]
            lbl = record["lbl"]
            eid = record["eid"]
            props = dict(node)
            seed_nodes.append((eid, lbl, props))
            seed_ids.add(eid)

            # Build a readable summary using the robust display-name helper
            display = node_display_name(props)
            seed_summaries.append(f"{lbl} '{display}'")

    if not seed_nodes:
        return [], []

    # --- Step B: 1-hop expansion (ALL direct relationships of seeds) ---
    # Uses startNode(r) / endNode(r) so the arrow always reflects the TRUE
    # stored direction in Neo4j (fixes Problem 2).
    one_hop_query = """
        MATCH (n)-[r]-(m)
        WHERE elementId(n) = $eid
        WITH r, startNode(r) AS a, endNode(r) AS b
        RETURN
            labels(a)[0]      AS a_label,
            properties(a)     AS a_props,
            elementId(a)      AS a_eid,
            type(r)           AS rel_type,
            properties(r)     AS rel_props,
            labels(b)[0]      AS b_label,
            properties(b)     AS b_props,
            elementId(b)      AS b_eid
    """

    seen_fact_keys = set()   # deduplication keys
    seed_facts = []          # facts touching a seed node (priority)
    hop2_facts = []          # 2-hop facts (lower priority)

    # Collect all nodes seen at 1-hop so we know what's "seed-related"
    one_hop_neighbor_ids = set()

    with driver.session() as session:
        for eid, _lbl, _props in seed_nodes:
            result = session.run(one_hop_query, eid=eid)
            for record in result:
                fact, fact_key = _format_fact(record)
                if fact_key not in seen_fact_keys:
                    seen_fact_keys.add(fact_key)
                    seed_facts.append(fact)
                # Track neighbor IDs for the 2-hop filter
                one_hop_neighbor_ids.add(record["a_eid"])
                one_hop_neighbor_ids.add(record["b_eid"])

    # --- Step C: 2-hop expansion (selective, avoids hubs) ---
    # For each 1-hop neighbor (that is NOT a seed and NOT a hub),
    # expand one more hop — but only keep facts where the far-end
    # node is itself seed-related (i.e. in seed_ids or one_hop_neighbor_ids).
    two_hop_query = """
        MATCH (mid)-[r]-(far)
        WHERE elementId(mid) = $mid_eid
          AND elementId(far) <> $mid_eid
        WITH r, startNode(r) AS a, endNode(r) AS b,
             elementId(far) AS far_eid
        RETURN
            labels(a)[0]      AS a_label,
            properties(a)     AS a_props,
            elementId(a)      AS a_eid,
            type(r)           AS rel_type,
            properties(r)     AS rel_props,
            labels(b)[0]      AS b_label,
            properties(b)     AS b_props,
            elementId(b)      AS b_eid,
            far_eid
    """

    # Determine which 1-hop neighbors to expand (skip seeds, skip hubs)
    candidates_to_expand = one_hop_neighbor_ids - seed_ids

    with driver.session() as session:
        for mid_eid in candidates_to_expand:
            # Check degree of this node — skip if it's a hub
            deg_result = session.run(
                "MATCH (n)-[r]-() WHERE elementId(n) = $eid RETURN count(r) AS deg",
                eid=mid_eid,
            )
            degree = deg_result.single()["deg"]
            if degree > HUB_DEGREE_THRESHOLD:
                continue  # hub node — do NOT expand

            result = session.run(two_hop_query, mid_eid=mid_eid)
            for record in result:
                far_eid = record["far_eid"]
                # Only keep if the far node connects back to something seed-related
                if far_eid in seed_ids or far_eid in one_hop_neighbor_ids:
                    fact, fact_key = _format_fact(record)
                    if fact_key not in seen_fact_keys:
                        seen_fact_keys.add(fact_key)
                        hop2_facts.append(fact)

    # --- Step D: Combine and cap ---
    # Seed-touching facts come first (most relevant), then 2-hop extras.
    all_facts = seed_facts + hop2_facts
    all_facts = all_facts[:MAX_FACTS]

    return all_facts, seed_summaries


def _format_fact(record):
    """
    Build a human-readable triple string from a query record,
    using the TRUE stored direction (startNode → endNode).
    Returns (fact_string, dedup_key).
    """
    a_label = record["a_label"]
    a_name = node_display_name(record["a_props"])
    b_label = record["b_label"]
    b_name = node_display_name(record["b_props"])
    rel_type = record["rel_type"]
    rel_props = record["rel_props"]

    # Format relationship properties (weight, avg, query_id, etc.)
    props_str = ""
    if rel_props:
        parts = [f"{k}:{v}" for k, v in rel_props.items()]
        props_str = " {" + ", ".join(parts) + "}"

    fact = (
        f"{a_label} '{a_name}' "
        f"-[{rel_type}{props_str}]-> "
        f"{b_label} '{b_name}'"
    )

    fact_key = (a_label, a_name, rel_type, b_label, b_name)
    return fact, fact_key


# =============================================================================
# 2. GENERATE — send evidence + question to the local LLM
# =============================================================================
OLLAMA_MODEL = "qwen2.5-coder:7b"

def generate(question, evidence):
    """
    Ask the LLM to answer the question using ONLY the retrieved facts.
    If the facts don't contain the answer, say so honestly.
    """
    if not evidence:
        return (
            "I could not find any relevant facts in the knowledge graph for this question. "
            "Please try rephrasing or asking about topics in the RepoReason graph."
        )

    # Format the evidence into a numbered list for the prompt
    evidence_block = "\n".join(f"  {i+1}. {fact}" for i, fact in enumerate(evidence))

    prompt = f"""You are a helpful assistant that answers questions using ONLY the knowledge graph facts provided below. Do NOT use any outside knowledge.

KNOWLEDGE GRAPH FACTS:
{evidence_block}

QUESTION: {question}

Instructions:
- Answer ONLY from the facts above. Do not add information that is not stated in the facts.
- Keep your answer to 2–4 sentences.
- Cite specific values (names, scores, weights) from the facts.
- When the question asks for the "best", "highest", or "top" something, compare ALL the numeric values present in the facts and pick the one with the largest number (e.g. the highest nDCG@10 score). Do NOT just pick the first one you see.
- If the facts do not contain enough information to answer, say: "The retrieved facts do not contain enough information to fully answer this question."

ANSWER:"""

    # Call the local Ollama model
    response = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0.1},  # low temperature for factual answers
    )

    return response["message"]["content"].strip()


# =============================================================================
# 3. ANSWER_QUESTION — retrieve then generate
# =============================================================================
def answer_question(question, driver):
    """Full GraphRAG pipeline: retrieve evidence, then generate a grounded answer."""
    evidence, seed_summaries = retrieve(question, driver)
    answer = generate(question, evidence)
    return evidence, answer


# =============================================================================
# 4. MAIN — run three demo questions
# =============================================================================
DEMO_QUESTIONS = [
    # Basic: single-entity lookup
    "What is the Hybrid ranking method and which signals does it use?",
    # Multi-hop: needs 2+ hops to connect paper → technique → ranking method → score
    "Which research paper introduced the technique behind the Dense ranking method, and what nDCG@10 score did the Dense method achieve?",
    # Research: repos + languages for a use-case
    "For a retrieval-augmented-generation chatbot idea, which repositories are strong fits, and what languages are they written in?",
]


def main():
    """Connect to Neo4j, run the three demo questions, and print results."""
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
        driver.verify_connectivity()
        print(f"✅ Connected to Neo4j at {NEO4J_URI}\n")
    except AuthError:
        print("❌ Neo4j authentication failed. Check credentials in .env.")
        sys.exit(1)
    except ServiceUnavailable:
        print("❌ Cannot reach Neo4j. Is the database running?")
        sys.exit(1)

    print("=" * 70)
    print("  RepoReason GraphRAG — Question → KG Retrieval → LLM Answer")
    print("=" * 70)

    for i, question in enumerate(DEMO_QUESTIONS, start=1):
        print(f"\n{'─' * 70}")
        print(f"  QUESTION {i}: {question}")
        print(f"{'─' * 70}")

        evidence, answer = answer_question(question, driver)

        # Print the retrieved KG evidence
        print(f"\n📋 RETRIEVED KG EVIDENCE ({len(evidence)} facts):")
        if evidence:
            for j, fact in enumerate(evidence, start=1):
                print(f"   {j:>2}. {fact}")
        else:
            print("   (no matching facts found)")

        # Print the LLM answer
        print(f"\n🤖 LLM ANSWER:")
        print(f"   {answer}")

    # Clean up
    driver.close()
    print(f"\n{'=' * 70}")
    print("🔒 Done. Driver closed.")


if __name__ == "__main__":
    main()
