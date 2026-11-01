"""
graph_app.py — Streamlit app for RepoReason graph-augmented repo search.

A live, reproducible local demo: searches GitHub, builds a Neo4j graph to
find more repos, and ranks everything with the hybrid ranker.

Usage:  streamlit run graphsearch/graph_app.py
Needs:  Neo4j running, Ollama running (nomic-embed-text + qwen2.5-coder:7b),
        internet for GitHub API, .env with NEO4J_* and GITHUB_TOKEN.
"""

import json
import os
import sys
from datetime import datetime, timezone

# --- Make project root + subfolders importable ---
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for p in [ROOT, os.path.join(ROOT, "c3"), os.path.join(ROOT, "graphsearch")]:
    if p not in sys.path:
        sys.path.insert(0, p)

import streamlit as st
from c3.github_client import search_repositories
from graphsearch.graph_rank import graph_search

# ollama is optional — only needed for "Why this fits"
try:
    import ollama
    OLLAMA_AVAILABLE = True
except Exception:
    ollama = None
    OLLAMA_AVAILABLE = False

EXPLAIN_MODEL = "qwen2.5-coder:7b"

# Where human-in-the-loop feedback is appended (one JSON object per line)
FEEDBACK_LOG = os.path.join(os.path.dirname(__file__), "feedback_log.jsonl")


def _feedback_key(query, full_name):
    """Session-state key for a (query, repo) judgment."""
    return f"{query}::{full_name}"


def record_feedback(query, full_name, judgment):
    """Store the judgment in session state and append it to the JSONL log."""
    st.session_state.setdefault("feedback", {})
    st.session_state["feedback"][_feedback_key(query, full_name)] = judgment

    entry = {
        "query": query,
        "repo": full_name,
        "judgment": judgment,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        with open(FEEDBACK_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        st.warning(f"Could not write feedback log: {e}")


# --- Page setup ---

st.set_page_config(page_title="RepoReason — Graph Search", layout="wide")
st.title("RepoReason — Graph-Augmented Repo Search")
st.caption(
    "Search GitHub, build a knowledge graph to discover more repos, and rank "
    "everything with a local hybrid model. Fully reproducible — runs on your machine."
)


# --- Search input ---

query = st.text_input("Describe your project idea", placeholder="e.g. RAG chatbot for PDF documents")
search_clicked = st.button("Search", type="primary")


# --- Run the pipeline on click, cache in session_state ---

if search_clicked:
    if not query.strip():
        st.error("Please enter a project idea.")
        st.stop()

    try:
        with st.spinner("Searching GitHub for initial repos…"):
            initial_repos = search_repositories(query.strip(), max_results=15)
        if not initial_repos:
            st.error(
                "GitHub returned no repos. Check your GITHUB_TOKEN and rate limit."
            )
            st.stop()
    except Exception as e:
        st.error(f"GitHub search failed: {e}")
        st.stop()

    try:
        with st.spinner("Building graph, expanding, and ranking… (this takes ~30s)"):
            results = graph_search(query.strip(), initial_repos)
    except Exception as e:
        st.error(
            f"Pipeline failed. Make sure Neo4j and Ollama are running.\n\n{e}"
        )
        st.stop()

    # Count how many are graph-found
    n_new = sum(1 for r in results if r["is_new"])

    # Store everything so re-sorts / explanations don't re-run
    st.session_state["results"] = results
    st.session_state["query"] = query.strip()
    st.session_state["n_initial"] = len(initial_repos)
    st.session_state["n_new"] = n_new
    st.session_state.setdefault("explanations", {})


# --- Display results from session_state ---

if "results" not in st.session_state:
    st.stop()

results = st.session_state["results"]
q = st.session_state["query"]
n_initial = st.session_state["n_initial"]
n_new = st.session_state["n_new"]
explanations = st.session_state["explanations"]

st.write("---")

# Summary line
st.markdown(
    f"**{n_initial}** initial repos → graph added **{n_new}** new → "
    f"**{len(results)}** total ranked for: *{q}*"
)

# --- Community stats (results are already in community-aware order) ---

# Distinct communities across the whole result set, in first-appearance order
community_order = []
for r in results:
    cid = r.get("community_id")
    if cid not in community_order:
        community_order.append(cid)
n_communities = len(community_order)

# Diversity = distinct communities among the shown top-k
SHOWN_TOP_K = 10
top_k = results[:SHOWN_TOP_K]
diversity = len({r.get("community_id") for r in top_k})

# Overall rank of each repo in the community-aware order (stable across views)
overall_rank = {r["full_name"]: i for i, r in enumerate(results, 1)}

# Communities caption
label = "community" if n_communities == 1 else "communities"
st.caption(
    f"🕸️ **{n_communities}** {label} found  ·  diversity: "
    f"**{diversity}** distinct {'community' if diversity == 1 else 'communities'} "
    f"in the top {len(top_k)}"
)


# --- Repo renderer (shared by both views) ---

def render_repo(rank, r):
    """Render a single repo card. `rank` is its overall community-aware rank."""
    with st.container(border=True):
        # Header: rank, linked name, badge if graph-found
        badge = "  🔗 *graph-found*" if r["is_new"] else ""
        url = r["url"] or "#"
        st.markdown(f"### {rank}. [{r['full_name']}]({url}){badge}")

        # Score + stars + language
        lang = r["language"] or "unknown"
        st.markdown(
            f"**Fit:** {r['fit_score']:.4f}  ·  ⭐ {r['stars']}  ·  {lang}"
        )

        # Description
        desc = r["description"] or "_(no description)_"
        if len(desc) > 200:
            desc = desc[:197] + "…"
        st.write(desc)

        # Topics
        if r["topics"]:
            st.caption("Topics: " + ", ".join(r["topics"]))

        # "Why this fits" button
        if st.button("💡 Why this fits", key=f"why_{rank}_{r['full_name']}"):
            if not OLLAMA_AVAILABLE:
                st.warning("ollama package not installed — can't explain.")
            else:
                try:
                    with st.spinner("Asking the local model…"):
                        prompt = (
                            f"User's project idea: {q}\n\n"
                            "Candidate repository (use ONLY these facts, invent nothing):\n"
                            f"- Name: {r['full_name']}\n"
                            f"- Description: {r['description'] or '(none)'}\n"
                            f"- Topics: {', '.join(r['topics']) or '(none)'}\n"
                            f"- Language: {r['language'] or '(unknown)'}\n\n"
                            "In ONE sentence, say whether this repository fits the "
                            "project idea and why, referring only to the facts above."
                        )
                        resp = ollama.chat(
                            model=EXPLAIN_MODEL,
                            messages=[{"role": "user", "content": prompt}],
                            options={"temperature": 0.1},
                        )
                        explanations[r["full_name"]] = resp["message"]["content"].strip()
                except Exception as e:
                    explanations[r["full_name"]] = f"(Error: {e})"

        # Show cached explanation
        if r["full_name"] in explanations:
            st.info(explanations[r["full_name"]])

        # --- Human-in-the-loop feedback controls ---
        current = st.session_state.get("feedback", {}).get(
            _feedback_key(q, r["full_name"])
        )
        JUDGMENTS = [
            ("👍 Relevant", "relevant"),
            ("👎 Not relevant", "not_relevant"),
            ("🔀 Wrong community", "wrong_community"),
        ]
        cols = st.columns(len(JUDGMENTS))
        for col, (label, value) in zip(cols, JUDGMENTS):
            with col:
                # Highlight the active judgment if one is already set
                btn_type = "primary" if current == value else "secondary"
                if st.button(
                    label,
                    key=f"fb_{value}_{rank}_{r['full_name']}",
                    type=btn_type,
                    use_container_width=True,
                ):
                    record_feedback(q, r["full_name"], value)
                    st.success(f"Recorded: {label}")
                    current = value

        # Reflect the current judgment on the row if one is already set
        if current:
            readable = dict((v, l) for l, v in JUDGMENTS)[current]
            st.caption(f"Your judgment: **{readable}**")


# --- View toggle: grouped by community vs flat ranked list ---

view_mode = st.radio(
    "View", ["Grouped by community (default)", "Flat ranked list"],
    horizontal=True,
)

if view_mode == "Flat ranked list":
    # Sort toggle only applies to the flat list
    sort_mode = st.radio(
        "Sort by", ["Fit score (default)", "Popularity (stars)"],
        horizontal=True,
    )
    if sort_mode == "Popularity (stars)":
        display = sorted(results, key=lambda r: r["stars"], reverse=True)
    else:
        display = results  # already sorted by fit_score

    for rank, r in enumerate(display, 1):
        render_repo(rank, r)

else:
    # Grouped view — one labeled section per community, community-aware order
    for cid in community_order:
        members = [r for r in results if r.get("community_id") == cid]
        header = "Community" if cid is None else f"Community {cid}"
        count = len(members)
        st.subheader(f"🧩 {header}  ·  {count} repo{'s' if count != 1 else ''}")
        for r in members:
            render_repo(overall_rank[r["full_name"]], r)
