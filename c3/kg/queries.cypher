// =============================================================================
// RepoReason Knowledge Graph — Queries
// =============================================================================
// Run these one at a time in Neo4j Browser, in order (1 through 5).
// =============================================================================


// -----------------------------------------------------------------------
// 1. Whole-graph overview
//    Returns every node and relationship so the full knowledge graph is
//    visualized in one picture. This is the quickest way to see the
//    structure and confirm the graph loaded correctly.
// -----------------------------------------------------------------------

MATCH (n)
OPTIONAL MATCH (n)-[r]->(m)
RETURN n, r, m;


// -----------------------------------------------------------------------
// 2. Find entities with MATCH
//    Lists every ProjectQuery with its id and query text. This confirms
//    the benchmark queries are present and lets you see what the system
//    was evaluated on.
// -----------------------------------------------------------------------

MATCH (q:ProjectQuery)
RETURN q.id AS query_id, q.query AS query_text
ORDER BY q.id;


// -----------------------------------------------------------------------
// 3. Traverse relationships — RAG query candidates and their relevance
//    For the RAG query (q1), follows HAS_CANDIDATE to its candidate
//    repositories, then LABELED_AS to their relevance labels. Returns
//    full paths so Neo4j Browser draws the subgraph: query → repos →
//    labels. This shows how real human judgments connect to the data.
// -----------------------------------------------------------------------

MATCH path = (q:ProjectQuery {id: "q1"})-[:HAS_CANDIDATE]->(r:Repository)-[:LABELED_AS]->(l:RelevanceLabel)
RETURN path;


// -----------------------------------------------------------------------
// 4. Multi-hop research query — Paper → Technique → RankingMethod → nDCG@10
//    Walks three hops: from a research Paper, through the Technique it
//    INTRODUCES, to every RankingMethod that IMPLEMENTS or BUILDS_ON that
//    technique, and finally to that method's SCORED relationship with the
//    nDCG@10 metric. This traces how foundational research flows into
//    concrete system performance. Ordered by score descending.
// -----------------------------------------------------------------------

MATCH (p:Paper)-[:INTRODUCES]->(t:Technique)<-[:IMPLEMENTS|BUILDS_ON]-(rm:RankingMethod)-[s:SCORED]->(m:Metric {name: "nDCG@10"})
RETURN p.title AS paper,
       t.name AS technique,
       rm.name AS method,
       s.avg AS ndcg_score
ORDER BY s.avg DESC;


// -----------------------------------------------------------------------
// 5. Research query — Hybrid method's signals, weights, and paper grounding
//    For the Hybrid ranking method, lists its five signals with their
//    weights (from the USES_SIGNAL relationship), and optionally the
//    research paper a signal is GROUNDED_IN. This shows how each signal
//    contributes to the final ranking and which are backed by a specific
//    paper. Ordered by weight descending.
// -----------------------------------------------------------------------

MATCH (rm:RankingMethod {name: "Hybrid"})-[u:USES_SIGNAL]->(sig:Signal)
OPTIONAL MATCH (sig)-[:GROUNDED_IN]->(p:Paper)
RETURN sig.name AS signal,
       sig.meaning AS meaning,
       u.weight AS weight,
       p.title AS grounded_in_paper
ORDER BY u.weight DESC;
