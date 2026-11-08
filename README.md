# RepoReason

**Graph-augmented, community-aware, explainable GitHub repository search.**

RepoReason ranks GitHub repositories by how well they *fit* a plain-English project
idea — not by stars alone — and explains every result so a user can trust it. For each
query it searches GitHub, builds a live Neo4j knowledge graph of the candidate repos,
uses that graph to recall strong repos the keyword search missed, fuses five signals
into a hybrid relevance score, detects communities with Leiden (Louvain fallback), and reranks for
diversity. A GraphRAG layer answers follow-up questions grounded in the graph, and a
human-in-the-loop feedback step (relevant / not / wrong-community) refines results.

> **Scope note.** This repository contains two stages of one project. The **capstone
> system described here and on the poster** is the repo-search system in
> [`graphsearch/`](graphsearch/) and [`c3/`](c3/). An **earlier milestone** — a
> bug-localization tool over the Click library (`app.py`, `retrieval.py`, `localize.py`,
> `eval/`, and the vendored `click/` source) — is kept at the repository root for
> history. If you are reproducing the poster, use the commands below, **not**
> `streamlit run app.py`.
> Link to the demo app - https://youtu.be/1YhbXrRfyNo
---

## Pipeline

```
Project idea (plain English)
  → GitHub search (~15 candidate repos)
    → Knowledge graph (Neo4j: SHARES_TOPIC + SIMILAR_TO via nomic-embed-text)
      → Graph-expand (2nd search → +recall; surfaces big repos)
        → Hybrid ranker (5 signals: semantic · popularity · recency · docs · license)
          → Community-aware rerank (Leiden → diversity, relevance-gated; Louvain fallback)
            → Grounded answer + GenAI explainer (GraphRAG · evidence paths)
              → Human feedback (relevant / not / wrong-community) ↺
```

## Repository layout

| Path | What it is |
|---|---|
| `graphsearch/graph_app.py` | **The capstone demo app** (Streamlit). Search → graph-expand → communities → ranked, explained results with feedback. |
| `graphsearch/graph_rank.py`, `graph_builder.py`, `graph_expand.py`, `communities.py` | Graph build, graph-driven recall, Leiden communities (Louvain fallback) + gated rerank. |
| `c3/rankers.py` | The four rankers: Native, BM25, Dense, Hybrid. |
| `c3/metrics.py` | Ranking metrics: `precision_at_k`, `recall_at_k`, `mrr`, `ndcg_at_k`. |
| `c3/run_all.py` | Ranker comparison over the benchmark → `c3/data/all_results.json`. |
| `c3/run_community_eval.py` | 3-way ablation (Traditional RAG / GraphRAG / Community-aware) → `c3/data/community_eval.json`. |
| `c3/run_baselines.py`, `c3/run_ablation.py`, `c3/run_gnn_eval.py` | Baseline, weight-sweep, and (rejected) GNN-enrichment experiments. |
| `c3/data/stats_validate.py` | 95% bootstrap CIs + paired tests on the saved results → `c3/data/stats_out/`. |
| `c3/data/repos.json` | 6 queries × their candidate repos (90 total). |
| `c3/data/to_label.csv` | Human relevance labels (0 / 1 / 2) for every candidate. |
| `c3/LABELING_CRITERIA.md` | The rubric used to assign the 0 / 1 / 2 labels. |
| `reproduce.py` | One command to regenerate every poster number **offline** from saved results. |
| `app.py`, `retrieval.py`, `localize.py`, `eval/`, `click/` | Earlier bug-localization milestone (see scope note). |

## Prerequisites

- **Python 3.10+** (developed on 3.12).
- **Neo4j** running locally (Neo4j Desktop or `docker run neo4j`), reachable via the
  `NEO4J_*` values in your `.env`.
- **Ollama** running, with two models pulled:
  ```bash
  ollama pull nomic-embed-text
  ollama pull qwen2.5-coder:7b
  ```
  `nomic-embed-text` powers the Dense/Hybrid embeddings and graph similarity;
  `qwen2.5-coder:7b` powers the "why this fits" explanations.
- A **GitHub personal access token** (classic, `public_repo` scope is enough) for the
  repository search API.

## Setup

```bash
# 1. Virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# 2. Dependencies
pip install -r requirements.txt

# 3. Secrets — copy the template and fill in your values
copy .env.example .env         # Windows   (cp on macOS/Linux)
#   then edit .env:
#     NEO4J_URI=bolt://localhost:7687
#     NEO4J_USERNAME=neo4j
#     NEO4J_PASSWORD=your-password
#     GITHUB_TOKEN=ghp_your_token
```

`.env` is git-ignored and must **never** be committed.

## Run the app

```bash
streamlit run graphsearch/graph_app.py
```
Open the URL Streamlit prints (usually `http://localhost:8501`), type a project idea
(e.g. *"RAG chatbot"*), and you'll get graph-expanded, community-grouped, explained
results with per-result feedback controls.

## Benchmark & evaluation

The benchmark is **6 project-idea queries** over **90 candidate repositories**, each
hand-labeled **0 / 1 / 2** against the rubric in
[`c3/LABELING_CRITERIA.md`](c3/LABELING_CRITERIA.md). Relevance is measured with
nDCG@10, P@5 and MRR; diversity with *distinct communities in the top-5* (Leiden;
Louvain returns the identical split on this pool, ARI = 1.0).

## Reproducing the poster numbers

**Offline (no services needed)** — regenerates every number and CI on the poster from
the committed results in `c3/data/`:
```bash
pip install numpy scipy
python reproduce.py
```

**Full re-run from scratch** — recomputes the results themselves (needs Neo4j + Ollama +
GitHub token configured as above, and will call the models, so it takes longer):
```bash
python c3/run_all.py                 # ranker comparison  -> c3/data/all_results.json
python -m c3.run_community_eval      # 3-way ablation     -> c3/data/community_eval.json
python c3/run_baselines.py           # baselines
python c3/run_gnn_eval.py            # GNN-enrichment experiment (rejected)
python c3/data/stats_validate.py     # 95% CIs            -> c3/data/stats_out/
```

## Results (6 queries, 95% bootstrap CIs)

- **Hybrid ranker** is best-or-tied on every metric (nDCG@10 **0.78**, P@5 **0.93**,
  MRR **1.00**). At n = 6 the nDCG margins over BM25 / Dense fall within the 95% CIs —
  a consistent lead, not yet a significant one.
- **Community-aware reranking** raises top-5 diversity **+35% (1.7 → 2.3)** — a paired
  gain of **+0.67, 95% CI [+0.17, +1.33]** that excludes zero — **at no relevance cost**
  (ΔnDCG +0.002, CI [−0.01, +0.01]). Every query that differs favors it (4/6 higher,
  2 tied, 0 worse). Against each query's community ceiling (2–3, mean 2.7),
  community-aware reaches **87% of achievable** diversity vs 56% for Traditional RAG.
- **Rejected dead end:** untrained GNN (GCN) embedding enrichment was net-negative
  (over-smoothing), so it is not in the final system.

## Limitations

- **Local services required** (Neo4j + Ollama), so this is a reproducible *local* demo,
  not a hosted one.
- **Small benchmark (n = 6 queries).** Differences are reported with CIs and effect
  sizes; the diversity gain is robust in direction, relevance gains are directional.
- **Single-annotator labels.** Relevance was labeled by one author against a written
  rubric; inter-annotator agreement is future work.

## Future work

Ecosystem edges (forks · dependencies · shared contributors); a larger benchmark via
LLM-assisted labeling with human spot-checks; a trained GAT on the richer graph; and a
GraphRAG Q&A + evidence-path panel in the live app.

## References

- Robertson & Zaragoza, *The Probabilistic Relevance Framework: BM25 and Beyond*.
- Nussbaum et al., *Nomic Embed: Training a Reproducible Long-Context Text Embedder*.

Stack: Neo4j · Ollama (nomic-embed-text, qwen2.5-coder:7b) · Streamlit · networkx ·
igraph + leidenalg (Leiden, Louvain fallback).
