# Import sys and os so we can add the project root to the import path
import sys
import os

# Add the project root to sys.path so imports work from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import json to load repos data for the smoke test
import json

# Import re to tokenize text for BM25
import re

# Import math for log in popularity scoring
import math

# Import datetime to parse pushed_at timestamps
from datetime import datetime, timezone

# Import BM25Okapi for keyword-based ranking
from rank_bm25 import BM25Okapi

# Import our embedding functions
from c3.embeddings import embed_text, cosine_similarity


# --- Module-level cache for embeddings (avoids re-computing the same text) ---
_embedding_cache = {}


def _get_embedding(text):
    """Get an embedding for text, using the cache to avoid duplicate calls."""
    if text not in _embedding_cache:
        _embedding_cache[text] = embed_text(text)
    return _embedding_cache[text]


# --- Helper: build a text representation of a repo for ranking ---

def repo_text(repo):
    """
    Combine a repo's name, description, and topics into one string.
    Handles missing or empty fields safely.
    """
    name = repo.get("full_name") or ""
    desc = repo.get("description") or ""
    topics = " ".join(repo.get("topics") or [])
    return f"{name} {desc} {topics}".strip()


# --- Helper: tokenize by lowercasing and splitting on non-alphanumeric ---

def _tokenize(text):
    return re.split(r"[^a-z0-9]+", text.lower())


# --- Helper: min-max normalize a list of values to 0..1 ---

def _min_max_normalize(values):
    """
    Scale values to 0..1 range. If all values are equal (or the list
    is empty), return 0.0 for all to avoid division by zero.
    """
    if not values:
        return []
    lo = min(values)
    hi = max(values)
    if hi == lo:
        return [0.0] * len(values)
    return [(v - lo) / (hi - lo) for v in values]


# --- Helper: parse an ISO date string to a Unix timestamp ---

def _parse_timestamp(date_str):
    """
    Parse an ISO 8601 date string (e.g. '2024-03-15T12:00:00Z') to a
    Unix timestamp float. Returns 0.0 if the string is missing or invalid.
    """
    if not date_str:
        return 0.0
    try:
        # Handle both 'Z' suffix and '+00:00' timezone formats
        cleaned = date_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        return dt.timestamp()
    except (ValueError, TypeError):
        return 0.0


# =====================================================================
# Ranker A — GitHub native order
# =====================================================================

def rank_native(query, repos):
    """Keep repos in the order they already appear (GitHub's default ranking)."""
    return [repo["full_name"] for repo in repos]


# =====================================================================
# Ranker B — BM25
# =====================================================================

def rank_bm25(query, repos):
    """Rank repos by BM25 keyword relevance of the query against repo text."""

    # Build the BM25 corpus from each repo's text
    corpus = [_tokenize(repo_text(r)) for r in repos]

    # Create the BM25 index
    bm25 = BM25Okapi(corpus)

    # Tokenize the query and score each repo
    query_tokens = _tokenize(query)
    scores = bm25.get_scores(query_tokens)

    # Pair full_names with scores and sort descending
    scored = [(repos[i]["full_name"], float(scores[i])) for i in range(len(repos))]
    scored.sort(key=lambda x: x[1], reverse=True)

    return [name for name, _ in scored]


# =====================================================================
# Ranker C — Dense (semantic embeddings)
# =====================================================================

def rank_dense(query, repos):
    """
    Rank repos by cosine similarity between the query embedding and
    each repo's text embedding. Uses nomic-embed-text prefixes:
    'search_query: ' for the query, 'search_document: ' for documents.
    """

    # Embed the query with the required prefix
    query_vec = _get_embedding("search_query: " + query)

    # Embed each repo's text and compute cosine similarity
    scored = []
    for repo in repos:
        doc_text = "search_document: " + repo_text(repo)
        doc_vec = _get_embedding(doc_text)
        sim = cosine_similarity(query_vec, doc_vec)
        scored.append((repo["full_name"], sim))

    # Sort by similarity descending
    scored.sort(key=lambda x: x[1], reverse=True)

    return [name for name, _ in scored]


# =====================================================================
# Ranker D — Hybrid (weighted combination of multiple signals)
# =====================================================================

def rank_hybrid(query, repos, weights=None):
    """
    Rank repos by a weighted combination of five signals, each
    min-max normalized to 0..1 within this query's candidate set.
    Returns (full_names_best_first, scored_list_with_details).
    If weights is provided (a dict), use it; otherwise use the defaults.
    """

    # --- Weight configuration (clearly labeled, easy to tune) ---
    # Use custom weights if provided, otherwise fall back to defaults
    if weights is None:
        weights = {
            "semantic":      0.55,
            "popularity":    0.15,
            "recency":       0.15,
            "documentation": 0.10,
            "license":       0.05,
        }

    n = len(repos)

    # --- Signal 1: Semantic similarity (same as rank_dense) ---
    query_vec = _get_embedding("search_query: " + query)
    raw_semantic = []
    for repo in repos:
        doc_text = "search_document: " + repo_text(repo)
        doc_vec = _get_embedding(doc_text)
        raw_semantic.append(cosine_similarity(query_vec, doc_vec))

    # --- Signal 2: Popularity = log(stars + 1) ---
    raw_popularity = [math.log(repo.get("stars", 0) + 1) for repo in repos]

    # --- Signal 3: Recency = pushed_at timestamp (newer = higher) ---
    raw_recency = [_parse_timestamp(repo.get("pushed_at")) for repo in repos]

    # --- Signal 4: Documentation quality ---
    # 1 point if description is non-empty, 1 point if topics is non-empty
    raw_documentation = []
    for repo in repos:
        score = 0
        if (repo.get("description") or "").strip():
            score += 1
        if repo.get("topics"):
            score += 1
        raw_documentation.append(score)

    # --- Signal 5: License presence ---
    # 1 if a license id is present and not None or "NOASSERTION", else 0
    raw_license = []
    for repo in repos:
        lic = repo.get("license")
        if lic and lic != "NOASSERTION":
            raw_license.append(1.0)
        else:
            raw_license.append(0.0)

    # --- Normalize all signals to 0..1 ---
    norm_semantic = _min_max_normalize(raw_semantic)
    norm_popularity = _min_max_normalize(raw_popularity)
    norm_recency = _min_max_normalize(raw_recency)
    norm_documentation = _min_max_normalize(raw_documentation)
    norm_license = _min_max_normalize(raw_license)

    # --- Compute the weighted final score for each repo ---
    scored = []
    for i in range(n):
        final = (
            weights["semantic"]      * norm_semantic[i]
            + weights["popularity"]    * norm_popularity[i]
            + weights["recency"]       * norm_recency[i]
            + weights["documentation"] * norm_documentation[i]
            + weights["license"]       * norm_license[i]
        )
        scored.append({
            "full_name": repos[i]["full_name"],
            "score": final,
            "semantic": norm_semantic[i],
            "popularity": norm_popularity[i],
            "recency": norm_recency[i],
            "documentation": norm_documentation[i],
            "license": norm_license[i],
        })

    # Sort by final score descending
    scored.sort(key=lambda x: x["score"], reverse=True)

    # Return just the names (best first) and the full scored list
    names = [s["full_name"] for s in scored]
    return names, scored

# =====================================================================
# Ranker D+ — Detailed hybrid (same logic, richer output)
# =====================================================================

def rank_detailed(query, repos, weights=None):
    """
    Rank repos using the EXACT same hybrid method as rank_hybrid
    (same five signals, same min-max normalization, same default weights,
    same weighted-sum score), but return richer per-repo dicts that
    include the original repo, normalized signals, and each signal's
    weighted contribution to the final score.

    Returns a list sorted best-first. Each element:
      {
        "repo":           <the original repo dict, unchanged>,
        "score":          <float: final hybrid score>,
        "signals":        {semantic, popularity, recency, documentation, license},
        "contributions":  {semantic, popularity, recency, documentation, license}
      }
    contributions[k] == weights[k] * signals[k], and they sum to score.
    """

    # Use custom weights if provided, otherwise fall back to defaults
    if weights is None:
        weights = {
            "semantic":      0.55,
            "popularity":    0.15,
            "recency":       0.15,
            "documentation": 0.10,
            "license":       0.05,
        }

    n = len(repos)

    # --- Compute the five raw signals (identical to rank_hybrid) ---

    query_vec = _get_embedding("search_query: " + query)
    raw_semantic = []
    for repo in repos:
        doc_text = "search_document: " + repo_text(repo)
        doc_vec = _get_embedding(doc_text)
        raw_semantic.append(cosine_similarity(query_vec, doc_vec))

    raw_popularity = [math.log(repo.get("stars", 0) + 1) for repo in repos]

    raw_recency = [_parse_timestamp(repo.get("pushed_at")) for repo in repos]

    raw_documentation = []
    for repo in repos:
        score = 0
        if (repo.get("description") or "").strip():
            score += 1
        if repo.get("topics"):
            score += 1
        raw_documentation.append(score)

    raw_license = []
    for repo in repos:
        lic = repo.get("license")
        if lic and lic != "NOASSERTION":
            raw_license.append(1.0)
        else:
            raw_license.append(0.0)

    # --- Normalize all signals to 0..1 ---
    norm_semantic = _min_max_normalize(raw_semantic)
    norm_popularity = _min_max_normalize(raw_popularity)
    norm_recency = _min_max_normalize(raw_recency)
    norm_documentation = _min_max_normalize(raw_documentation)
    norm_license = _min_max_normalize(raw_license)

    # --- Build the detailed results ---
    detailed = []
    for i in range(n):
        signals = {
            "semantic":      norm_semantic[i],
            "popularity":    norm_popularity[i],
            "recency":       norm_recency[i],
            "documentation": norm_documentation[i],
            "license":       norm_license[i],
        }

        # Each contribution = weight * normalized signal
        contributions = {k: weights[k] * signals[k] for k in weights}

        # Final score = sum of contributions (same as rank_hybrid's formula)
        final = sum(contributions.values())

        detailed.append({
            "repo": repos[i],
            "score": final,
            "signals": signals,
            "contributions": contributions,
        })

    # Sort by final score descending (same ordering as rank_hybrid)
    detailed.sort(key=lambda x: x["score"], reverse=True)

    return detailed


# --- Smoke test: load first query from repos.json, run hybrid, print top 5 ---


if __name__ == "__main__":

    # Load the repo data
    repos_path = os.path.join("c3", "data", "repos.json")
    with open(repos_path, "r", encoding="utf-8") as f:
        all_repos = json.load(f)

    # Take the first query
    first_qid = sorted(all_repos.keys())[0]
    query_text = all_repos[first_qid]["query"]
    repos = all_repos[first_qid]["repos"]

    print(f"Query [{first_qid}]: \"{query_text}\"")
    print(f"Candidates: {len(repos)} repos\n")

    print("Running hybrid ranker...\n")

    names, scored = rank_hybrid(query_text, repos)

    print("Top 5 results:\n")
    for i, entry in enumerate(scored[:5], start=1):
        print(f"  {i}. {entry['full_name']}")
        print(f"     score={entry['score']:.4f}  "
              f"sem={entry['semantic']:.3f}  "
              f"pop={entry['popularity']:.3f}  "
              f"rec={entry['recency']:.3f}  "
              f"doc={entry['documentation']:.3f}  "
              f"lic={entry['license']:.3f}")
        print()
