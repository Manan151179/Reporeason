# Labeling Criteria — RepoReason Ground Truth

This file defines how every repository in `c3/data/to_label.csv` is scored. The same standard applies to all queries (q1–q6 and any added later), so labels stay consistent and metrics stay comparable across queries.

## Who the ground truth serves

RepoReason should help anyone with a project idea find repos that help them build it, directly or indirectly. Labels therefore judge each repo for three audiences:

- **B — Beginner:** wants to understand the concept and workflow, or copy a working starter.
- **D — Developer:** wants reusable code, architecture, or a base to build a real product on.
- **R — Researcher:** wants techniques, comparisons, baselines, or curated sources to study.

## The scale

| Score | Meaning |
|---|---|
| **2 — Highly relevant** | You would genuinely build on or closely study this for the query's project. |
| **1 — Relevant** | Related and partly useful: a piece of the solution, a tangential tool, a decent tutorial, or a good repo with serious caveats. |
| **0 — Not relevant** | Does not help build this project: wrong problem, unusable, or teaches the wrong pattern. |

**The rule for a 2:** the repo passes query fit **and** either
(a) it is a strong partner for at least one audience and still usable by a second, **or**
(b) it offers something no other repo in this query's pool does.

## Factors, checked in this order

1. **Query fit (gate).** Does it actually do what the query describes? A repo that shares keywords but solves a different problem is a 0, whatever its quality.
2. **Unique value.** If two repos offer the same thing, the better one gets the credit. A near-duplicate is capped at 1, regardless of stars. This builds diversity into the labels.
3. **Beginner value.** Runs quickly, free or cheap, correct instructions, a plain explanation (diagram, article, screenshots), code small enough to read.
4. **Developer value.** Reusable structure, API, database, memory, citations or sources, tests, Docker, deployment, permissive license.
5. **Researcher value.** Shows techniques or comparisons (alternative methods, baselines, evaluation), or an architecture worth studying.
6. **Barriers.** Paid services, cloud lock-in, GPU needs, or long setup chains lower the score for any audience that can't clear them.
7. **Trust.** Stars and forks, official organisation, license, documentation, recent activity. Stars are a signal, never the definition of quality.
8. **Transparency.** Can you see how the core technique works, or is it hidden behind managed services?

## Repo-type rules (for consistency across queries)

| Repo type | Usual ceiling |
|---|---|
| Working app or system that does what the query describes | up to 2 |
| Framework or library you would build the project with | up to 2 |
| Tutorial or notebook series that teaches the core workflow | 2 if unique in the pool, otherwise 1 |
| Collection of many mini-projects | usually 1 |
| Awesome-list, survey, or paper list | max 1 (research discovery only); 0 if off-topic |
| Tangential tool (evaluation, logging, one component) | max 1 |
| Repo locked to a narrower domain than the query asks for | usually 1 |
| Dataset only (no code) | max 1 (research use) |
| Different problem that shares keywords | 0 |
| Same author's near-identical repo that adds nothing over their other one | 0 |
| No code, no setup, broken beyond use, or teaches the wrong pattern | 0 |

Two clarifications that came up while labeling q2–q6:

- **Judge the code, not the README.** If the README promises a feature (routing, AI, ML matching) that the code does not contain, score what is actually there. A template or scaffold whose core feature is missing is a 0.
- **Suspected but unverified breakage is a `CHECK:`, not a 0.** Old pinned dependencies or dead APIs that *probably* fail get flagged in the note; only breakage visible in the repo itself (empty files, missing modules, obsolete build system) can justify a 0.

## Procedure for each query

1. Read every repo's README, full file tree, and the code behind any key claim. Never score from the name alone.
2. Apply the query-fit gate first and mark the 0s.
3. Group the rest by what they offer and spot near-duplicates.
4. Pick the 2s: the best repo in each distinct group that meets the rule for a 2.
5. Everything else that passed the gate is a 1.
6. Write the note (format below).
7. Sanity check the distribution. Expect roughly 3–5 twos out of 15. If you land outside 2–6, re-check before saving; this is a check, not a quota.

## Notes format

Each row has exactly one number in `relevance` and one note in `notes`. Nothing else in `relevance`.

```
[audiences] what it is and why this score | main caveat
```

- Audience tags: `B`, `D`, `R`; add `*` for a strong fit (e.g. `[B*,D]`). Use `[-]` for 0s.
- Prefix `CHECK:` when part of the judgment could not be verified (e.g. a sub-folder could not be opened).
- Keep it to one or two short sentences.

Example: `[B*,D,R] Guided build: Colab, local Streamlit, free cloud deploy; RAG-vs-ChatGPT baseline script | needs OpenAI key (Groq alternative)`

## How the metrics use these labels

- **nDCG** uses the graded 0/1/2 scores directly.
- **Precision@5, Recall@10, MRR** use a binary cut: relevant = score ≥ 1.
- A stricter view (relevant = 2 only) can also be reported.
- The `notes` column is ignored by the scoring code. It feeds the diversity analysis and Challenge 4 synthesis.

## Evidence standard and known limits

- Each repo was shallow-cloned, so judgments use the README, the full file tree (including sub-folders), license, last commit date, and spot-checks of the code behind key claims. Code is not run.
- Anything that still could not be verified is flagged with `CHECK:` in the note.
- Labels come from a single labeler. The written rubric is the main protection against inconsistency; a second labeler scoring a sample and comparing agreement would strengthen it further.

## Worked example — q1 "retrieval augmented generation RAG chatbot application"

Four 2s, each covering a different need:

- **Lizhecheng02/RAG-ChatBot:** the best guided build for beginners.
- **mesutdmn/Chat-With-Your-PDF:** a clean, reusable pipeline.
- **Bensmail-anis/RAGbot:** the only production-shaped full stack.
- **HenryHengLUO/Retrieval-Augmented-Generation-Intro-Project:** compares retrieval techniques.

Two calls illustrate the rules:

- **syahvan/simple-doc-chatbot** is excellent for beginners but scored 1, because the near-duplicate cap applies (Lizhecheng covers the same stack with more).
- **aws-samples/sample-cdk-rds-pg-memdb-text-to-sql** scored 0, because it fails the query-fit gate (text-to-SQL, not document RAG).
