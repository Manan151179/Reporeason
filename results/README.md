# Results index

Run `python reproduce.py` from the repo root to regenerate all of these offline.

---

## Benchmark definition

| | |
|---|---|
| **Queries** | 6 plain-English project-idea queries (`q1`–`q6`) |
| **Candidates** | 90 GitHub repositories (15 per query), hand-labeled **0** (not relevant) / **1** (relevant) / **2** (highly relevant) against the rubric in [`c3/LABELING_CRITERIA.md`](../c3/LABELING_CRITERIA.md) |
| **Relevance metrics** | nDCG@10 (graded), P@5, MRR |
| **Diversity metric** | Distinct communities in top-5 (`div@5`) — Leiden detection; Louvain fallback |
| **Statistics** | 95% bootstrap CIs + paired Wilcoxon tests (n = 6); computed by [`c3/data/stats_validate.py`](../c3/data/stats_validate.py) |

---

## File → contents → claim

| File | Contents | Claim supported |
|---|---|---|
| [`all_results.json`](all_results.json) | Per-query and averaged nDCG@10, P@5, R@10, MRR for all four rankers: Native, BM25, Dense, Hybrid | **Hybrid best-or-tied on every metric** — nDCG@10 **0.78**, P@5 **0.93**, MRR **1.00** (averages over 6 queries) |
| [`community_eval.json`](community_eval.json) | Per-query nDCG@10, P@5, div@5 for the 3-way ablation: Traditional RAG / GraphRAG / Community-aware | Community-aware raises div@5 **1.7 → 2.3** (+35%) vs Traditional RAG; relevance unchanged (ΔnDCG +0.002) |
| [`per_query_metrics.csv`](per_query_metrics.csv) | One row per (system, query): all four rankers + three ablation systems, with their raw metric values and community ceiling | Per-query breakdown underlying every average and CI; shows 4/6 queries higher div@5 with Community-aware, 2/6 tied, 0/6 worse |
| [`stats_summary.csv`](stats_summary.csv) | Pairwise comparisons with bootstrap delta, 95% CI, and paired Wilcoxon p-value | **Community vs GraphRAG div@5**: paired gain **+0.667**, 95% CI **[+0.167, +1.333]** (excludes zero); ΔnDCG **+0.002**, CI **[−0.007, +0.011]** (cost-free). Hybrid vs all baselines on nDCG: directional lead, margins within CIs at n = 6 |
| [`figures/ranker_comparison.png`](figures/ranker_comparison.png) | Bar chart: nDCG@10, P@5, MRR for Native / BM25 / Dense / Hybrid | Hybrid is best-or-tied on every bar; nDCG@10 = 0.78 |
| [`figures/ablation_relevance_diversity.png`](figures/ablation_relevance_diversity.png) | Side-by-side: nDCG@10 and div@5 for Traditional RAG / GraphRAG / Community-aware | Community-aware gains diversity (+35%) with flat relevance |
| [`figures/diversity_per_query.png`](figures/diversity_per_query.png) | Per-query div@5 for all three ablation systems | Shows the direction of the gain across all 6 queries (4 higher, 2 tied) |
| [`figures/community_graph_q1.png`](figures/community_graph_q1.png) | Graph visualisation of communities detected on query q1 | Illustrates the Leiden partition; Leiden ≡ Louvain on this pool (ARI = 1.0) |
| [`figures/popularity_weight_sweep.png`](figures/popularity_weight_sweep.png) | nDCG@10 vs popularity signal weight (ablation) | Motivates the chosen weight of 0.25 for the popularity signal in the hybrid ranker |
| [`figures/hybrid_signal_weights.png`](figures/hybrid_signal_weights.png) | Bar chart of the five hybrid signal weights (semantic 0.45, popularity 0.25, recency 0.15, documentation 0.10, license 0.05) | Documents the final weight configuration used in `c3/rankers.py · rank_hybrid()` |

