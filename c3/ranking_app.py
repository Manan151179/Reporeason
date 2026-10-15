# Import streamlit to build the web app
import streamlit as st

# Import os and sys so we can locate this file and fix the import path
import os
import sys

# Import json to load the saved benchmark pool
import json

# Import datetime to turn pushed_at timestamps into "3 months ago" text
from datetime import datetime, timezone


# --- Make the app's own folder importable ---
# When launched as `streamlit run c3/ranking_app.py`, the working directory is
# the project root, not c3/. Adding this file's folder to sys.path lets the
# plain "from rankers import ..." / "from github_client import ..." imports work.
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

# The ranker is required — if it can't import, the app can't do its job.
from rankers import rank_detailed

# The live-search client is optional: without it (or without a GITHUB_TOKEN),
# the user can still rank the saved benchmark pool. Import defensively.
try:
    from github_client import search_repositories
    GITHUB_AVAILABLE = True
    GITHUB_IMPORT_ERROR = ""
except Exception as e:
    search_repositories = None
    GITHUB_AVAILABLE = False
    GITHUB_IMPORT_ERROR = str(e)

# ollama is only needed for the per-repo "Why this fits" explanation. Import it
# defensively too, so the ranking UI still works if it isn't installed.
try:
    import ollama
    OLLAMA_AVAILABLE = True
except Exception:
    ollama = None
    OLLAMA_AVAILABLE = False


# --- Configuration ---

# The chat model used for the one-sentence "Why this fits" explanation
EXPLAIN_MODEL = "qwen2.5-coder:7b"

# The five signal keys rank_detailed reports, with friendly labels for display
SIGNAL_LABELS = {
    "semantic": "Semantic match",
    "popularity": "Popularity (stars)",
    "recency": "Recency (last push)",
    "documentation": "Documentation",
    "license": "License",
}


# --- Load the saved benchmark pool, relative to this file ---

@st.cache_data
def load_pool():
    """
    Load c3/data/repos.json using a path built from this file's location.
    Shape: { query_id: { "query": str, "repos": [ ... ] } }.
    Returns {} if the file is missing or unreadable.
    """
    repos_path = os.path.join(HERE, "data", "repos.json")
    try:
        with open(repos_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


# --- Helper: human-friendly "last push" from an ISO timestamp ---

def human_last_push(pushed_at):
    """
    Turn an ISO 8601 timestamp (e.g. '2024-03-15T12:00:00Z') into a short
    relative string like '3 months ago'. Returns 'unknown' if it can't parse.
    """
    if not pushed_at:
        return "unknown"
    try:
        # Handle both the 'Z' suffix and explicit '+00:00' offsets
        dt = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
    except (ValueError, TypeError, AttributeError):
        return "unknown"

    # Seconds between now (UTC) and the push time
    now = datetime.now(timezone.utc)
    seconds = (now - dt).total_seconds()
    if seconds < 0:
        return "just now"

    # Walk down from years to minutes and use the first unit that fits
    minute, hour, day = 60, 3600, 86400
    year, month, week = 365 * day, 30 * day, 7 * day
    for span, label in [
        (year, "year"), (month, "month"), (week, "week"),
        (day, "day"), (hour, "hour"), (minute, "minute"),
    ]:
        count = int(seconds // span)
        if count >= 1:
            return f"{count} {label}{'s' if count != 1 else ''} ago"
    return "just now"


# --- Helper: ask the local model for a one-sentence fit explanation ---

def explain_fit(query, repo):
    """
    Ask the local model for ONE sentence on whether this repo fits the query,
    using only the repo's name, description, topics, and language. Returns the
    sentence, or a clear error string if the call fails.
    """
    if not OLLAMA_AVAILABLE:
        return "(Could not explain: the 'ollama' package is not available.)"

    # Gather only the facts the model is allowed to use
    name = repo.get("full_name") or "(no name)"
    desc = (repo.get("description") or "").strip() or "(no description provided)"
    topics = ", ".join(repo.get("topics") or []) or "(none)"
    language = repo.get("language") or "(unknown)"

    prompt = (
        f"User's project idea: {query}\n\n"
        "Candidate repository (use ONLY these facts, invent nothing):\n"
        f"- Name: {name}\n"
        f"- Description: {desc}\n"
        f"- Topics: {topics}\n"
        f"- Language: {language}\n\n"
        "In ONE sentence, say whether this repository fits the project idea and "
        "why, referring only to the facts above. Do not invent features that are "
        "not stated. If the description is missing or too vague to tell, say the "
        "fit is uncertain."
    )

    try:
        response = ollama.chat(
            model=EXPLAIN_MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.1},
        )
        return response["message"]["content"].strip()
    except Exception as e:
        return f"(Could not get an explanation. Is Ollama running? Error: {e})"


# --- Helper: reset per-ranking state so a new ranking starts clean ---

def reset_review_state():
    """Clear accept/reject verdicts and cached explanations from a prior ranking."""
    st.session_state["reviews"] = {}
    st.session_state["explanations"] = {}


# --- Page setup ---

st.set_page_config(page_title="RepoReason — Ranking", layout="wide")
st.title("RepoReason — Repository Ranking")
st.write(
    "Rank candidate repositories for a project idea using the hybrid ranker "
    "(semantic + popularity + recency + documentation + license), then inspect "
    "why each repo ranks where it does and accept or reject it."
)

# Load the saved pool once
pool = load_pool()


# --- Sidebar: choose the candidate source and trigger ranking ---

st.sidebar.header("Candidates")

source = st.sidebar.radio(
    "Where should candidates come from?",
    ["Saved benchmark pool", "Live GitHub search"],
)

# These hold whatever the user selected, resolved when the button is clicked
selected_query = ""
selected_qid = None
live_query = ""

if source == "Saved benchmark pool":
    if not pool:
        st.sidebar.error(
            "Could not load c3/data/repos.json. Build the pool first, or switch "
            "to live search."
        )
    else:
        # Build friendly labels like 'q1 — retrieval augmented generation ...'
        qids = sorted(pool.keys())

        def _label(qid):
            text = pool[qid].get("query", "")
            short = text if len(text) <= 55 else text[:52] + "..."
            return f"{qid} — {short}"

        selected_qid = st.sidebar.selectbox(
            "Query", qids, format_func=_label,
        )
        selected_query = pool[selected_qid].get("query", "")

else:  # Live GitHub search
    if not GITHUB_AVAILABLE:
        st.sidebar.warning(
            "Live search is unavailable because github_client could not be "
            "imported. Use the saved benchmark pool instead."
        )
        if GITHUB_IMPORT_ERROR:
            st.sidebar.caption(f"Import error: {GITHUB_IMPORT_ERROR}")
    live_query = st.sidebar.text_input(
        "Project idea to search for",
        value="retrieval augmented generation RAG chatbot application",
    )

rank_clicked = st.sidebar.button("Rank repositories", type="primary")


# --- Ranking: runs only on button click, then stores results in session_state ---

if rank_clicked:

    # 1. Resolve the candidate repos and the query text from the chosen source
    query = ""
    repos = []

    if source == "Saved benchmark pool":
        if not pool or selected_qid is None:
            st.error("No saved pool to rank. Build c3/data/repos.json first.")
            st.stop()
        query = selected_query
        repos = pool[selected_qid].get("repos", [])

    else:  # Live GitHub search
        if not GITHUB_AVAILABLE:
            st.error(
                "Live search is unavailable (github_client could not be "
                "imported). Switch to the saved benchmark pool."
            )
            st.stop()
        if not live_query.strip():
            st.error("Please enter a project idea to search for.")
            st.stop()
        query = live_query.strip()
        with st.spinner("Searching GitHub..."):
            repos = search_repositories(query, max_results=15)
        if not repos:
            st.error(
                "No repositories came back. Check your GITHUB_TOKEN and rate "
                "limit, or try the saved benchmark pool."
            )
            st.stop()

    # 2. Rank the candidates. rank_detailed needs the local embedding model
    #    (nomic-embed-text via Ollama), so guard the call.
    try:
        with st.spinner("Ranking repositories..."):
            detailed = rank_detailed(query, repos)
    except Exception as e:
        st.error(
            "Ranking failed. Ollama is probably not running — the hybrid ranker "
            "needs the local embedding model 'nomic-embed-text'. Start Ollama and "
            "pull it with:  ollama pull nomic-embed-text"
        )
        st.code(str(e))
        st.stop()

    # 3. Store the results and query, and reset per-repo review/explanation state
    st.session_state["ranked"] = detailed
    st.session_state["ranked_query"] = query
    reset_review_state()


# --- Results: rendered from session_state so button clicks don't re-rank ---

if "ranked" in st.session_state:
    detailed = st.session_state["ranked"]
    query = st.session_state["ranked_query"]

    # Make sure the review/explanation dicts exist (defensive)
    st.session_state.setdefault("reviews", {})
    st.session_state.setdefault("explanations", {})
    reviews = st.session_state["reviews"]
    explanations = st.session_state["explanations"]

    st.write("---")
    st.subheader(f"Results for: {query}")

    # One-line tally of accepted / rejected / total
    accepted = sum(1 for v in reviews.values() if v == "accepted")
    rejected = sum(1 for v in reviews.values() if v == "rejected")
    st.caption(
        f"✅ {accepted} accepted · ❌ {rejected} rejected · {len(detailed)} total"
    )

    # Render each ranked repo in its own bordered container
    for i, entry in enumerate(detailed, start=1):
        repo = entry["repo"]
        score = entry["score"]
        signals = entry["signals"]
        contributions = entry["contributions"]

        full_name = repo.get("full_name") or "(unknown repo)"
        html_url = repo.get("html_url") or "#"

        with st.container(border=True):

            # Header: rank, linked name, hybrid score, stars
            verdict = reviews.get(full_name)
            badge = ""
            if verdict == "accepted":
                badge = "  ✅"
            elif verdict == "rejected":
                badge = "  ❌"
            st.markdown(
                f"### {i}. [{full_name}]({html_url}){badge}"
            )
            st.markdown(
                f"**Score:** {score:.4f}  ·  ⭐ {repo.get('stars', 0)}"
            )

            # Meta row: language · last push · license
            language = repo.get("language") or "unknown"
            last_push = human_last_push(repo.get("pushed_at"))
            license_id = repo.get("license") or "none"
            st.markdown(
                f"**Language:** {language}  ·  **Last push:** {last_push}  ·  "
                f"**License:** {license_id}"
            )

            # Description and (optional) topics
            st.write(repo.get("description") or "_(no description)_")
            topics = repo.get("topics") or []
            if topics:
                st.caption("Topics: " + ", ".join(topics))

            # "Why it ranks here": one row per signal
            st.markdown("**Why it ranks here**")
            for key, label in SIGNAL_LABELS.items():
                strength = signals.get(key, 0.0)
                contrib = contributions.get(key, 0.0)
                c1, c2, c3 = st.columns([3, 5, 2])
                with c1:
                    st.write(label)
                with c2:
                    # progress expects 0..1; clamp just in case
                    st.progress(max(0.0, min(1.0, strength)))
                with c3:
                    st.write(f"+{contrib:.3f}")

            # Action buttons with keys unique per repo
            b1, b2, b3 = st.columns(3)
            with b1:
                if st.button("💡 Why this fits", key=f"why_{i}_{full_name}"):
                    with st.spinner("Asking the local model..."):
                        explanations[full_name] = explain_fit(query, repo)
            with b2:
                if st.button("✅ Accept", key=f"acc_{i}_{full_name}"):
                    reviews[full_name] = "accepted"
                    st.rerun()
            with b3:
                if st.button("❌ Reject", key=f"rej_{i}_{full_name}"):
                    reviews[full_name] = "rejected"
                    st.rerun()

            # Show the cached explanation once generated
            if full_name in explanations:
                st.info(explanations[full_name])
