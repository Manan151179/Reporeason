#!/usr/bin/env python3
"""
reproduce.py — regenerate every RepoReason poster number OFFLINE from the results
already committed in c3/data/. No GitHub, Neo4j, or Ollama.

Pure stdlib here; numpy/scipy are used only inside the c3/data/stats_validate.py
subprocess (CIs are not reimplemented — that script owns them). stats_validate's
community-ceiling step needs Ollama and degrades to "unavailable" when it is down,
so this stays fully offline. Exits non-zero if an expected file is missing or any
poster check FAILs, so it doubles as a CI gate.
"""

import os
import sys
import csv
import json
import subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "c3", "data")
TOL = 0.01


def need(path):
    if not os.path.exists(path):
        print(f"\nMISSING EXPECTED FILE: {path}")
        sys.exit(2)
    return path


def main():
    print("=" * 70)
    print("Reproducing RepoReason poster numbers (offline, from c3/data/)")
    print("=" * 70)

    # --- 2. Ranker comparison table ---
    all_res = json.load(open(need(os.path.join(DATA, "all_results.json")), encoding="utf-8"))
    avg = all_res["averages"]
    print("\nRanker comparison (averages over 6 queries):")
    print(f"  {'Ranker':<10}{'nDCG@10':>9}{'P@5':>8}{'MRR':>8}")
    for disp, k in [("Native", "A_Native"), ("BM25", "B_BM25"),
                    ("Dense", "C_Dense"), ("Hybrid", "D_Hybrid")]:
        a = avg[k]
        print(f"  {disp:<10}{a['nDCG@10']:>9.4f}{a['P@5']:>8.4f}{a['MRR']:>8.4f}")

    # --- 3. 3-way ablation table + per-query diversity ---
    comm = json.load(open(need(os.path.join(DATA, "community_eval.json")), encoding="utf-8"))
    cavg = comm["averages"]
    print("\n3-way ablation (averages over 6 queries):")
    print(f"  {'System':<18}{'nDCG@10':>9}{'P@5':>8}{'div@5':>8}")
    for disp, k in [("Traditional RAG", "RAG"), ("GraphRAG", "GraphRAG"),
                    ("Community-aware", "Community")]:
        a = cavg[k]
        print(f"  {disp:<18}{a['nDCG@10']:>9.4f}{a['P@5']:>8.4f}{a['div@5']:>8.4f}")

    print("\n  Per-query diversity@5:")
    print(f"    {'query':<6}{'RAG':>5}{'GraphRAG':>10}{'Community':>11}")
    for row in comm["per_query"]:
        print(f"    {row['query_id']:<6}{row['RAG']['div@5']:>5}"
              f"{row['GraphRAG']['div@5']:>10}{row['Community']['div@5']:>11}")

    # --- 4. Reuse stats_validate.py (subprocess; it owns the CIs & writes the summary CSV) ---
    sv = need(os.path.join(DATA, "stats_validate.py"))
    print("\n" + "=" * 70)
    print("Running c3/data/stats_validate.py (bootstrap CIs + Wilcoxon):")
    print("=" * 70)
    sys.stdout.flush()  # flush our buffered output so it precedes the subprocess's
    rc = subprocess.run([sys.executable, sv], cwd=ROOT).returncode
    if rc != 0:
        print(f"\nstats_validate.py exited {rc} — stopping.")
        sys.exit(rc)

    # --- 5. POSTER CLAIM -> REPRODUCED checklist ---
    summary = {}
    with open(need(os.path.join(DATA, "stats_out", "stats_summary.csv")), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            summary[(r["comparison"], r["metric"])] = r
    cvg = summary[("Community vs GraphRAG", "div@5")]
    cvg_ndcg = summary[("Community vs GraphRAG", "nDCG@10")]

    # Only the poster TARGETS are hardcoded; every actual is read from the files above.
    checks = [
        ("Hybrid nDCG@10 = 0.78", 0.78, avg["D_Hybrid"]["nDCG@10"]),
        ("Community-vs-GraphRAG div gain = +0.67", 0.67, float(cvg["delta"])),
        ("Community-vs-GraphRAG div CI low = +0.17", 0.17, float(cvg["ci_low"])),
        ("Community-vs-GraphRAG div CI high = +1.33", 1.33, float(cvg["ci_high"])),
        ("Community-vs-GraphRAG nDCG delta = +0.002", 0.002, float(cvg_ndcg["delta"])),
    ]

    print("\n" + "=" * 70)
    print(f"POSTER CLAIM -> REPRODUCED  (tolerance {TOL})")
    print("=" * 70)
    all_ok = True
    for label, target, actual in checks:
        ok = abs(actual - target) <= TOL
        all_ok &= ok
        print(f"  [{'OK' if ok else 'FAIL'}]  {label:<44} target={target:+.4f}  actual={actual:+.4f}")

    # --- 7. Re-run commands note ---
    print("\nNote — to regenerate the source results (needs GitHub/Ollama/Neo4j), run from repo root:")
    print("  python -m c3.run_all             # -> c3/data/all_results.json")
    print("  python -m c3.run_community_eval  # -> c3/data/community_eval.json")
    print("  python c3/data/stats_validate.py # -> c3/data/stats_out/*.csv")

    # --- 6. CI gate ---
    if not all_ok:
        print("\nSome poster checks FAILed.")
        sys.exit(1)
    print("\nAll poster numbers reproduced.")


if __name__ == "__main__":
    main()
