"""
stats_validate.py — statistical validation on top of the EXISTING benchmark results.

seed = 42 everywhere (numpy). This script does NOT recompute or change any ranking /
scoring logic and hardcodes no poster numbers. It loads the per-query metric vectors
that the existing pipelines already saved:
    * ranker comparison  -> c3/data/all_results.json      (run_all.py)
    * 3-way ablation     -> c3/data/community_eval.json   (run_community_eval.py)
and ASSERTS that the mean of each per-query vector reproduces that file's reported
average (to the precision the file stores it at) before any statistics are computed —
this is the silent-drift guard. Metric functions are the project's own
(c3.metrics / graphsearch.communities); none are reimplemented here.

Ablation vectors are LOADED (not recomputed) on purpose: detect_communities() uses
Leiden, which is seeded randomly, so a fresh run would not reproduce the stored
Community ranking / div@5 and would false-trigger the drift guard. The only thing not
stored anywhere is each query's community ceiling (# communities in the pool); that is
recomputed best-effort by reusing build_community_graph()/detect_communities() and
needs Ollama — if the model is down it prints "unavailable" and the stats still run.

Usage:  python c3/data/stats_validate.py
"""

import os
import sys
import csv
import json
import warnings

import numpy as np
from scipy.stats import wilcoxon

HERE = os.path.dirname(os.path.abspath(__file__))              # c3/data
PROJECT_ROOT = os.path.dirname(os.path.dirname(HERE))          # repo root
sys.path.insert(0, PROJECT_ROOT)

SEED = 42
N_BOOT = 10000
ASSERT_TOL = 1e-6

# Metrics are NOT reimplemented here. The per-query values loaded below were produced by
# the project's own c3.metrics (nDCG@10/P@5/MRR) and graphsearch.communities (diversity@5)
# via run_all.py / run_community_eval.py; the community-ceiling path below reuses
# graphsearch.build_community_graph/detect_communities directly.


# =====================================================================
# Load per-query metric vectors from the existing result files
# =====================================================================

def _load_json(name):
    with open(os.path.join(HERE, name), "r", encoding="utf-8") as f:
        return json.load(f)


def load_rankers():
    """
    Ranker comparison from all_results.json (full precision).
    Returns (vectors, averages, qids, round_dp).
      vectors[system][metric] -> np.array over queries
    """
    data = _load_json("all_results.json")
    # per_query uses short keys A/B/C/D; averages use A_Native etc.
    key = {"Native": "A", "BM25": "B", "Dense": "C", "Hybrid": "D"}
    avg_key = {"Native": "A_Native", "BM25": "B_BM25", "Dense": "C_Dense", "Hybrid": "D_Hybrid"}
    metrics = ["nDCG@10", "P@5", "MRR"]

    qids = [row["query_id"] for row in data["per_query"]]
    vectors = {s: {m: np.array([row[key[s]][m] for row in data["per_query"]], dtype=float)
                   for m in metrics}
               for s in key}
    averages = {s: {m: data["averages"][avg_key[s]][m] for m in metrics} for s in key}
    return vectors, averages, qids, None  # all_results stores full precision


def load_ablation():
    """
    3-way ablation from community_eval.json (stored rounded to 4 dp).
    Display names map to the stored keys: Traditional RAG->RAG, Community-aware->Community.
    Returns (vectors, averages, qids, round_dp=4).
    """
    data = _load_json("community_eval.json")
    key = {"Traditional RAG": "RAG", "GraphRAG": "GraphRAG", "Community-aware": "Community"}
    metrics = ["nDCG@10", "P@5", "div@5"]

    qids = [row["query_id"] for row in data["per_query"]]
    vectors = {s: {m: np.array([row[key[s]][m] for row in data["per_query"]], dtype=float)
                   for m in metrics}
               for s in key}
    averages = {s: {m: data["averages"][key[s]][m] for m in metrics} for s in key}
    return vectors, averages, qids, 4  # community_eval stores 4 dp


def assert_means(group, vectors, averages, round_dp):
    """Drift guard: mean of each per-query vector must reproduce the file's average.

    When the file stores the average at a fixed precision (round_dp), the recomputed
    mean is rounded to that same precision before the 1e-6 comparison, so the check is
    'does the vector reproduce the reported number', not 'does it reproduce lost digits'.
    """
    for s, mets in vectors.items():
        for m, vec in mets.items():
            mean = float(vec.mean())
            reported = averages[s][m]
            check = round(mean, round_dp) if round_dp is not None else mean
            if abs(check - reported) > ASSERT_TOL:
                print(f"\nMISMATCH in {group}: {s} / {m}: "
                      f"mean(per-query)={mean:.8f} (->{check}) != reported {reported}")
                print("Per-query vectors do not reproduce the saved averages — stopping to "
                      "avoid analysing drifted data.")
                sys.exit(1)
    print(f"  [{group}] drift guard OK: all {sum(len(v) for v in vectors.values())} "
          f"system/metric means reproduce the saved averages.")


# =====================================================================
# Statistics (numpy seeded; scipy Wilcoxon exact)
# =====================================================================

def bootstrap_mean_ci(x, rng, n=N_BOOT):
    idx = rng.integers(0, len(x), size=(n, len(x)))
    means = x[idx].mean(axis=1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return float(lo), float(hi)


def bootstrap_delta_ci(a, b, rng, n=N_BOOT):
    """Paired percentile bootstrap of the delta: resample query indices once, apply to both."""
    m = len(a)
    idx = rng.integers(0, m, size=(n, m))
    deltas = a[idx].mean(axis=1) - b[idx].mean(axis=1)
    lo, hi = np.percentile(deltas, [2.5, 97.5])
    return float(lo), float(hi)


def paired_wilcoxon(a, b):
    """Exact two-sided paired Wilcoxon signed-rank. Returns (stat, p)."""
    d = a - b
    if np.allclose(d, 0.0):
        return float("nan"), 1.0  # all ties: no evidence of a difference
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res = wilcoxon(a, b, method="exact", zero_method="wilcox")
        return float(res.statistic), float(res.pvalue)
    except ValueError:
        # happens when every nonzero difference is dropped / all ties
        return float("nan"), 1.0


# =====================================================================
# Community ceilings (best-effort; the only quantity not already stored)
# =====================================================================

def compute_ceilings(qids):
    """# communities in each query's pool, via the existing graph pipeline. Needs Ollama."""
    try:
        from c3.embeddings import embed_text
        from graphsearch.communities import build_community_graph, detect_communities
        repos_path = os.path.join(HERE, "repos.json")
        with open(repos_path, "r", encoding="utf-8") as f:
            all_queries = json.load(f)
    except Exception as e:  # import or file failure
        print(f"  (ceilings unavailable: {e})")
        return {q: None for q in qids}

    ceilings = {}
    for qid in qids:
        repos = all_queries.get(qid, {}).get("repos", [])
        if not repos:
            ceilings[qid] = None
            continue
        try:
            embeddings = []
            for repo in repos:
                name = repo.get("full_name") or ""
                desc = repo.get("description") or ""
                topics = repo.get("topics") or []
                text = f"{name} {desc} {' '.join(topics)}".strip()
                embeddings.append(embed_text("search_document: " + text))
            G = build_community_graph(repos, embeddings)
            communities, _ = detect_communities(G)
            ceilings[qid] = len(communities)
        except RuntimeError as e:  # Ollama not running / model missing
            print(f"  (ceilings unavailable: {e})")
            return {q: None for q in qids}
    return ceilings


# =====================================================================
# Output helpers
# =====================================================================

def build_comparisons(rk_vec, ab_vec):
    """Return list of (comparison_label, metric, vec_A, vec_B) for every key comparison."""
    comps = []
    # Ranker: Hybrid vs Native/BM25/Dense on nDCG@10, P@5, MRR
    for other in ["Native", "BM25", "Dense"]:
        for m in ["nDCG@10", "P@5", "MRR"]:
            comps.append((f"Hybrid vs {other}", m, rk_vec["Hybrid"][m], rk_vec[other][m]))
    # Ablation: on nDCG@10, P@5, div@5
    ablation_pairs = [
        ("GraphRAG vs Traditional RAG", "GraphRAG", "Traditional RAG"),
        ("Community vs GraphRAG", "Community-aware", "GraphRAG"),
        ("Community vs Traditional RAG", "Community-aware", "Traditional RAG"),
    ]
    for label, a, b in ablation_pairs:
        for m in ["nDCG@10", "P@5", "div@5"]:
            comps.append((label, m, ab_vec[a][m], ab_vec[b][m]))
    return comps


def main():
    rng = np.random.default_rng(SEED)
    np.random.seed(SEED)  # belt-and-braces: the task asks to "set numpy seed 42"

    print("=" * 78)
    print("STEP 1 — load per-query vectors from existing results & assert vs saved averages")
    print("=" * 78)
    rk_vec, rk_avg, rk_qids, rk_dp = load_rankers()
    ab_vec, ab_avg, ab_qids, ab_dp = load_ablation()
    assert_means("rankers", rk_vec, rk_avg, rk_dp)
    assert_means("ablation", ab_vec, ab_avg, ab_dp)
    assert rk_qids == ab_qids, "query id order differs between the two result files"
    qids = rk_qids
    n = len(qids)
    print(f"  queries (n={n}): {', '.join(qids)}")

    # --- Community ceilings (auxiliary; not used in the stats) ---
    print("\nCommunity ceiling per query (max possible diversity@5 = min(5, ceiling)):")
    ceilings = compute_ceilings(qids)
    for q in qids:
        c = ceilings[q]
        print(f"  {q}: {'unavailable' if c is None else c}")

    # =================================================================
    print("\n" + "=" * 78)
    print(f"STEP 2 — per-system mean + 95% paired bootstrap CI ({N_BOOT} resamples, seed={SEED})")
    print("=" * 78)
    for group, vectors, metrics in [
        ("RANKERS", rk_vec, ["nDCG@10", "P@5", "MRR"]),
        ("ABLATION", ab_vec, ["nDCG@10", "P@5", "div@5"]),
    ]:
        print(f"\n[{group}]")
        print(f"  {'System':<18}{'Metric':<10}{'mean':>8}   95% bootstrap CI")
        print("  " + "-" * 56)
        for s in vectors:
            for m in metrics:
                vec = vectors[s][m]
                lo, hi = bootstrap_mean_ci(vec, rng)
                print(f"  {s:<18}{m:<10}{vec.mean():>8.4f}   [{lo:.4f}, {hi:.4f}]")

    # --- Comparisons: delta, delta CI, Wilcoxon exact ---
    print("\n" + "=" * 78)
    print("Key comparisons — paired delta (A-B), 95% bootstrap CI of delta, Wilcoxon exact")
    print("=" * 78)
    print(f"  {'Comparison':<30}{'Metric':<9}{'meanA':>7}{'meanB':>7}{'delta':>8}"
          f"   {'delta 95% CI':<20}{'W':>5}{'p':>8}")
    print("  " + "-" * 94)

    summary_rows = []
    for label, m, a, b in build_comparisons(rk_vec, ab_vec):
        mean_a, mean_b = float(a.mean()), float(b.mean())
        delta = mean_a - mean_b
        lo, hi = bootstrap_delta_ci(a, b, rng)
        w, p = paired_wilcoxon(a, b)
        w_str = "  nan" if np.isnan(w) else f"{w:>5.1f}"
        print(f"  {label:<30}{m:<9}{mean_a:>7.4f}{mean_b:>7.4f}{delta:>+8.4f}"
              f"   [{lo:>+7.4f},{hi:>+7.4f}]{w_str}{p:>8.4f}")
        summary_rows.append({
            "comparison": label, "metric": m,
            "mean_A": round(mean_a, 6), "mean_B": round(mean_b, 6),
            "delta": round(delta, 6), "ci_low": round(lo, 6), "ci_high": round(hi, 6),
            "wilcoxon_stat": "" if np.isnan(w) else round(w, 4),
            "p_value": round(p, 6), "n": n,
        })

    print(f"\n  NOTE: n={n}. The exact two-sided Wilcoxon p-value cannot go below ~0.031 at "
          f"n=6, so the\n  bootstrap CIs are the primary evidence and the p-values are "
          f"secondary (underpowered).")

    # =================================================================
    # STEP 3 — write CSVs
    # =================================================================
    out_dir = os.path.join(HERE, "stats_out")
    os.makedirs(out_dir, exist_ok=True)

    # per_query_metrics.csv: one row per (system, query), every metric used
    pq_path = os.path.join(out_dir, "per_query_metrics.csv")
    pq_cols = ["group", "system", "query_id", "nDCG@10", "P@5", "MRR", "div@5", "community_ceiling"]
    with open(pq_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=pq_cols)
        w.writeheader()
        for group, vectors, metrics in [
            ("ranker", rk_vec, ["nDCG@10", "P@5", "MRR"]),
            ("ablation", ab_vec, ["nDCG@10", "P@5", "div@5"]),
        ]:
            for s in vectors:
                for i, q in enumerate(qids):
                    row = {"group": group, "system": s, "query_id": q,
                           "community_ceiling": ceilings[q] if ceilings[q] is not None else ""}
                    for m in metrics:
                        row[m] = round(float(vectors[s][m][i]), 6)
                    w.writerow(row)

    # stats_summary.csv: exact columns requested
    ss_path = os.path.join(out_dir, "stats_summary.csv")
    ss_cols = ["comparison", "metric", "mean_A", "mean_B", "delta",
               "ci_low", "ci_high", "wilcoxon_stat", "p_value", "n"]
    with open(ss_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=ss_cols)
        w.writeheader()
        w.writerows(summary_rows)

    print(f"\nWrote {pq_path}")
    print(f"Wrote {ss_path}")


if __name__ == "__main__":
    main()
