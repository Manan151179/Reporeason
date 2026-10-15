// =============================================================================
// RepoReason Knowledge Graph — Neo4j Cypher
// =============================================================================
// Reset first with:  MATCH (n) DETACH DELETE n;
//
// Then paste everything below into the Neo4j Browser query box and click Run.
// =============================================================================

CREATE

// =====================================================================
// ProjectQuery nodes — the 6 benchmark queries from queries.json
// =====================================================================

(q1:ProjectQuery {id: "q1", query: "retrieval augmented generation RAG chatbot application"}),
(q2:ProjectQuery {id: "q2", query: "job matching recommendation system machine learning"}),
(q3:ProjectQuery {id: "q3", query: "real-time navigation routing app with maps"}),
(q4:ProjectQuery {id: "q4", query: "healthcare patient dashboard analytics"}),
(q5:ProjectQuery {id: "q5", query: "sentiment analysis social media NLP"}),
(q6:ProjectQuery {id: "q6", query: "image classification deep learning web app"}),

// =====================================================================
// RelevanceLabel nodes — the three graded relevance tiers
// =====================================================================

(rel2:RelevanceLabel {grade: 2, label: "Strong fit"}),
(rel1:RelevanceLabel {grade: 1, label: "Partial fit"}),
(rel0:RelevanceLabel {grade: 0, label: "Off-target"}),

// =====================================================================
// Language nodes — distinct languages from selected repos
// =====================================================================

(langPython:Language    {name: "Python"}),
(langJupyter:Language   {name: "Jupyter Notebook"}),
(langTypeScript:Language{name: "TypeScript"}),
(langDart:Language      {name: "Dart"}),
(langJava:Language      {name: "Java"}),
(langJavaScript:Language{name: "JavaScript"}),
(langHTML:Language       {name: "HTML"}),
(langTSQL:Language       {name: "TSQL"}),
(langCSharp:Language     {name: "C#"}),
(langCSS:Language        {name: "CSS"}),

// =====================================================================
// License nodes — distinct licenses from selected repos
// =====================================================================

(licMIT:License   {spdx_id: "MIT"}),
(licApache:License{spdx_id: "Apache-2.0"}),

// =====================================================================
// Repository nodes — top 2-3 per query (real data from repos.json + to_label.csv)
// =====================================================================

// --- q1 repos ---
(r_henry:Repository {
  full_name: "HenryHengLUO/Retrieval-Augmented-Generation-Intro-Project",
  html_url:  "https://github.com/HenryHengLUO/Retrieval-Augmented-Generation-Intro-Project",
  stars: 70, pushed_at: "2024-01-27T13:35:09Z",
  description: "This project aims to introduce and demonstrate the practical applications of RAG using Python code in a Jupyter Notebook environment."
}),
(r_lizhecheng:Repository {
  full_name: "Lizhecheng02/RAG-ChatBot",
  html_url:  "https://github.com/Lizhecheng02/RAG-ChatBot",
  stars: 41, pushed_at: "2025-01-29T06:33:53Z",
  description: "A basic application using langchain, streamlit, and large language models to build a system for Retrieval-Augmented Generation (RAG) based on documents."
}),
(r_bensmail:Repository {
  full_name: "Bensmail-anis/RAGbot---Generative_AI-RAG-Application",
  html_url:  "https://github.com/Bensmail-anis/RAGbot---Generative_AI-RAG-Application",
  stars: 16, pushed_at: "2025-03-01T21:10:09Z",
  description: "A powerful chatbot assistant leveraging Retrieval-Augmented Generation (RAG) to answer questions from multiple PDF documents."
}),

// --- q2 repos ---
(r_pacchu:Repository {
  full_name: "Pacchu04/Candidate-Matching-App",
  html_url:  "https://github.com/Pacchu04/Candidate-Matching-App",
  stars: 3,
  description: "A Recommendation System using Machine Learning Techniques to match candidates to job openings."
}),
(r_ullas:Repository {
  full_name: "ullasgowda11/AI-Based-Job-Recommendation-System",
  html_url:  "https://github.com/ullasgowda11/AI-Based-Job-Recommendation-System",
  stars: 1,
  description: "A scalable AI-powered job recommendation platform that matches candidates with thousands of job opportunities using hybrid machine learning."
}),
(r_gowtham:Repository {
  full_name: "Gowthampalanivel-07/AI-CARRIER-DEVELOPMENT-SYSTEM",
  html_url:  "https://github.com/Gowthampalanivel-07/AI-CARRIER-DEVELOPMENT-SYSTEM",
  stars: 1,
  description: "Full-stack AI-driven career development system built with Python and modern frontend technologies."
}),

// --- q3 repos ---
(r_hord:Repository {
  full_name: "HordRicJr/HordMaps",
  html_url:  "https://github.com/HordRicJr/HordMaps",
  stars: 6, pushed_at: "2025-05-30T00:33:48Z",
  description: "HordMaps - A modern navigation app built with Flutter and powered by Azure Maps."
}),
(r_navigo:Repository {
  full_name: "Navigo-Kenya/navigo",
  html_url:  "https://github.com/Navigo-Kenya/navigo",
  stars: 2,
  description: "Navigo helps riders find nearby matatu/bus stages, preview walking routes, and navigate with real-time, low-latency guidance."
}),
(r_campus:Repository {
  full_name: "arghya0003/Campus-Nav",
  html_url:  "https://github.com/arghya0003/Campus-Nav",
  stars: 1,
  description: "Campus navigation app with turn-by-turn directions and real-time routing using Google Maps APIs."
}),

// --- q4 repos ---
(r_dashboard:Repository {
  full_name: "Dashboard-Design/Healthcare-Analytics-Streamlit-Dashboard",
  html_url:  "https://github.com/Dashboard-Design/Healthcare-Analytics-Streamlit-Dashboard",
  stars: 5,
  description: "A Streamlit-powered dashboard for hospital performance analysis, patient clustering, and billing optimization."
}),
(r_medsync:Repository {
  full_name: "SAdreasgamer/MedSync",
  html_url:  "https://github.com/SAdreasgamer/MedSync",
  stars: 3,
  description: "MedSync is a distributed healthcare platform built with 6 microservices (Java + Python)."
}),
(r_yuan:Repository {
  full_name: "yuan-code/Healthcare_Data_in_SQL_and_Visualization_in_Tableau",
  html_url:  "https://github.com/yuan-code/Healthcare_Data_in_SQL_and_Visualization_in_Tableau",
  stars: 15,
  description: "This healthcare analytics project uses SQL queries to extract insights from patient data."
}),

// --- q5 repos ---
(r_ali:Repository {
  full_name: "AliAmini93/TelecomSent",
  html_url:  "https://github.com/AliAmini93/TelecomSent",
  stars: 27,
  description: "Developed BERT, LSTM, TFIDF, and Word2Vec models to analyze social media data."
}),
(r_yeezy:Repository {
  full_name: "yeezyyoba/amharic-sentiment-analysis",
  html_url:  "https://github.com/yeezyyoba/amharic-sentiment-analysis",
  stars: 18,
  description: "Amharic sentiment analysis using multilingual transformers (Afro-XLM-R) fine-tuned on AfriSenti."
}),
(r_acampillos:Repository {
  full_name: "acampillos/social-media-nlp",
  html_url:  "https://github.com/acampillos/social-media-nlp",
  stars: 14,
  description: "Sentiment analysis with pre-trained language models using TweetEval."
}),

// --- q6 repos ---
(r_shreya:Repository {
  full_name: "shreyakmukherjee/Image-Classification-WebApp",
  html_url:  "https://github.com/shreyakmukherjee/Image-Classification-WebApp",
  stars: 4,
  description: "A Streamlit-based web application for image classification using two models: a custom CNN for CIFAR-10 and a pre-trained MobileNetV2."
}),
(r_mateo:Repository {
  full_name: "Mateorovere/Dog_breed_classification",
  html_url:  "https://github.com/Mateorovere/Dog_breed_classification",
  stars: 4,
  description: "Dog Breed Recognition is a web app that uses deep learning to classify dog breeds from images."
}),
(r_satellite:Repository {
  full_name: "pixelpawnshop/Satellite-Imagery-Land-Use-Classification",
  html_url:  "https://github.com/pixelpawnshop/Satellite-Imagery-Land-Use-Classification",
  stars: 3,
  description: "Interactive web app for land use classification from Sentinel-2 satellite imagery using deep learning."
}),

// =====================================================================
// Signal nodes — the five hybrid ranker signals (from rankers.py)
// =====================================================================

(sigSemantic:Signal      {name: "semantic",      meaning: "Cosine similarity between query and repo text embeddings (nomic-embed-text)"}),
(sigPopularity:Signal    {name: "popularity",    meaning: "Log-scaled GitHub star count: log(stars + 1)"}),
(sigRecency:Signal       {name: "recency",       meaning: "How recently the repo was pushed (newer = higher)"}),
(sigDocumentation:Signal {name: "documentation", meaning: "Whether the repo has a description and topics (0-2 points)"}),
(sigLicense:Signal       {name: "license",       meaning: "Whether the repo has a recognized open-source license"}),

// =====================================================================
// RankingMethod nodes — the four rankers evaluated
// =====================================================================

(rmNative:RankingMethod {name: "Native",  description: "GitHub default search ranking order"}),
(rmBM25:RankingMethod   {name: "BM25",    description: "BM25Okapi keyword relevance over repo metadata text"}),
(rmDense:RankingMethod  {name: "Dense",   description: "Cosine similarity of nomic-embed-text embeddings"}),
(rmHybrid:RankingMethod {name: "Hybrid",  description: "Weighted combination of semantic, popularity, recency, documentation, and license signals"}),

// =====================================================================
// Metric nodes — the four evaluation metrics
// =====================================================================

(metNDCG:Metric  {name: "nDCG@10",    meaning: "Normalized Discounted Cumulative Gain at rank 10 — measures graded relevance quality"}),
(metP5:Metric    {name: "Precision@5", meaning: "Fraction of the top-5 results that are relevant (label >= 1)"}),
(metR10:Metric   {name: "Recall@10",   meaning: "Fraction of all relevant repos found in the top-10 results"}),
(metMRR:Metric   {name: "MRR",         meaning: "Reciprocal rank of the first relevant result"}),

// =====================================================================
// Paper nodes — three research sources
// =====================================================================

(papBM25:Paper {
  authors: "Robertson & Zaragoza",
  year: 2009,
  title: "The Probabilistic Relevance Framework: BM25 and Beyond"
}),
(papNomic:Paper {
  authors: "Nussbaum et al.",
  year: 2024,
  title: "Nomic Embed: Training a Reproducible Long Context Text Embedder",
  arxiv: "2402.01613"
}),
(papNDCG:Paper {
  authors: "Jarvelin & Kekalainen",
  year: 2002,
  title: "Cumulated Gain-Based Evaluation of IR Techniques"
}),

// =====================================================================
// Technique nodes — retrieval techniques used
// =====================================================================

(techBM25:Technique   {name: "BM25 keyword scoring",         description: "Probabilistic term-frequency weighting for keyword retrieval"}),
(techDense:Technique  {name: "Dense embedding retrieval",    description: "Semantic similarity via neural text embeddings and cosine distance"}),
(techHybrid:Technique {name: "Hybrid multi-signal ranking",  description: "Weighted combination of semantic, metadata, and quality signals"}),

// =====================================================================
// RELATIONSHIPS — ProjectQuery -> Repository (candidate repos)
// =====================================================================

(q1)-[:HAS_CANDIDATE]->(r_henry),
(q1)-[:HAS_CANDIDATE]->(r_lizhecheng),
(q1)-[:HAS_CANDIDATE]->(r_bensmail),
(q2)-[:HAS_CANDIDATE]->(r_pacchu),
(q2)-[:HAS_CANDIDATE]->(r_ullas),
(q2)-[:HAS_CANDIDATE]->(r_gowtham),
(q3)-[:HAS_CANDIDATE]->(r_hord),
(q3)-[:HAS_CANDIDATE]->(r_navigo),
(q3)-[:HAS_CANDIDATE]->(r_campus),
(q4)-[:HAS_CANDIDATE]->(r_dashboard),
(q4)-[:HAS_CANDIDATE]->(r_medsync),
(q4)-[:HAS_CANDIDATE]->(r_yuan),
(q5)-[:HAS_CANDIDATE]->(r_ali),
(q5)-[:HAS_CANDIDATE]->(r_yeezy),
(q5)-[:HAS_CANDIDATE]->(r_acampillos),
(q6)-[:HAS_CANDIDATE]->(r_shreya),
(q6)-[:HAS_CANDIDATE]->(r_mateo),
(q6)-[:HAS_CANDIDATE]->(r_satellite),

// =====================================================================
// RELATIONSHIPS — Repository -> RelevanceLabel (real labels from to_label.csv)
// =====================================================================

(r_henry)-[:LABELED_AS      {query_id: "q1"}]->(rel2),
(r_lizhecheng)-[:LABELED_AS {query_id: "q1"}]->(rel2),
(r_bensmail)-[:LABELED_AS   {query_id: "q1"}]->(rel2),
(r_pacchu)-[:LABELED_AS     {query_id: "q2"}]->(rel2),
(r_ullas)-[:LABELED_AS      {query_id: "q2"}]->(rel2),
(r_gowtham)-[:LABELED_AS    {query_id: "q2"}]->(rel2),
(r_hord)-[:LABELED_AS       {query_id: "q3"}]->(rel2),
(r_navigo)-[:LABELED_AS     {query_id: "q3"}]->(rel2),
(r_campus)-[:LABELED_AS     {query_id: "q3"}]->(rel2),
(r_dashboard)-[:LABELED_AS  {query_id: "q4"}]->(rel2),
(r_medsync)-[:LABELED_AS    {query_id: "q4"}]->(rel2),
(r_yuan)-[:LABELED_AS       {query_id: "q4"}]->(rel2),
(r_ali)-[:LABELED_AS        {query_id: "q5"}]->(rel2),
(r_yeezy)-[:LABELED_AS      {query_id: "q5"}]->(rel2),
(r_acampillos)-[:LABELED_AS {query_id: "q5"}]->(rel2),
(r_shreya)-[:LABELED_AS     {query_id: "q6"}]->(rel2),
(r_mateo)-[:LABELED_AS      {query_id: "q6"}]->(rel2),
(r_satellite)-[:LABELED_AS  {query_id: "q6"}]->(rel2),

// =====================================================================
// RELATIONSHIPS — Repository -> Language
// =====================================================================

(r_henry)-[:WRITTEN_IN]->(langJupyter),
(r_lizhecheng)-[:WRITTEN_IN]->(langJupyter),
(r_bensmail)-[:WRITTEN_IN]->(langTypeScript),
(r_pacchu)-[:WRITTEN_IN]->(langHTML),
(r_ullas)-[:WRITTEN_IN]->(langJupyter),
(r_gowtham)-[:WRITTEN_IN]->(langPython),
(r_hord)-[:WRITTEN_IN]->(langDart),
(r_navigo)-[:WRITTEN_IN]->(langTypeScript),
(r_campus)-[:WRITTEN_IN]->(langTypeScript),
(r_dashboard)-[:WRITTEN_IN]->(langJupyter),
(r_medsync)-[:WRITTEN_IN]->(langJava),
(r_yuan)-[:WRITTEN_IN]->(langTSQL),
(r_ali)-[:WRITTEN_IN]->(langJupyter),
(r_yeezy)-[:WRITTEN_IN]->(langJupyter),
(r_acampillos)-[:WRITTEN_IN]->(langJupyter),
(r_shreya)-[:WRITTEN_IN]->(langPython),
(r_mateo)-[:WRITTEN_IN]->(langJavaScript),
(r_satellite)-[:WRITTEN_IN]->(langPython),

// =====================================================================
// RELATIONSHIPS — Repository -> License (only repos with a real license)
// =====================================================================

(r_bensmail)-[:HAS_LICENSE]->(licMIT),
(r_hord)-[:HAS_LICENSE]->(licMIT),
(r_dashboard)-[:HAS_LICENSE]->(licMIT),
(r_acampillos)-[:HAS_LICENSE]->(licMIT),

// =====================================================================
// RELATIONSHIPS — RankingMethod(Hybrid) -> Signal (real weights from rankers.py)
// =====================================================================

(rmHybrid)-[:USES_SIGNAL {weight: 0.55}]->(sigSemantic),
(rmHybrid)-[:USES_SIGNAL {weight: 0.15}]->(sigPopularity),
(rmHybrid)-[:USES_SIGNAL {weight: 0.15}]->(sigRecency),
(rmHybrid)-[:USES_SIGNAL {weight: 0.10}]->(sigDocumentation),
(rmHybrid)-[:USES_SIGNAL {weight: 0.05}]->(sigLicense),

// =====================================================================
// RELATIONSHIPS — RankingMethod -> Metric (real avg scores from all_results.json)
// =====================================================================

// Native
(rmNative)-[:SCORED {avg: 0.7243}]->(metNDCG),
(rmNative)-[:SCORED {avg: 0.8333}]->(metP5),
(rmNative)-[:SCORED {avg: 0.6719}]->(metR10),
(rmNative)-[:SCORED {avg: 0.9167}]->(metMRR),

// BM25
(rmBM25)-[:SCORED {avg: 0.7383}]->(metNDCG),
(rmBM25)-[:SCORED {avg: 0.9000}]->(metP5),
(rmBM25)-[:SCORED {avg: 0.6857}]->(metR10),
(rmBM25)-[:SCORED {avg: 0.9167}]->(metMRR),

// Dense
(rmDense)-[:SCORED {avg: 0.7426}]->(metNDCG),
(rmDense)-[:SCORED {avg: 0.9000}]->(metP5),
(rmDense)-[:SCORED {avg: 0.6857}]->(metR10),
(rmDense)-[:SCORED {avg: 1.0000}]->(metMRR),

// Hybrid
(rmHybrid)-[:SCORED {avg: 0.7823}]->(metNDCG),
(rmHybrid)-[:SCORED {avg: 0.9333}]->(metP5),
(rmHybrid)-[:SCORED {avg: 0.7181}]->(metR10),
(rmHybrid)-[:SCORED {avg: 1.0000}]->(metMRR),

// =====================================================================
// RELATIONSHIPS — RankingMethod -> Technique
// =====================================================================

(rmBM25)-[:IMPLEMENTS]->(techBM25),
(rmDense)-[:IMPLEMENTS]->(techDense),
(rmHybrid)-[:IMPLEMENTS]->(techHybrid),
(rmHybrid)-[:BUILDS_ON]->(techBM25),
(rmHybrid)-[:BUILDS_ON]->(techDense),

// =====================================================================
// RELATIONSHIPS — Paper -> Technique (research grounding)
// =====================================================================

(papBM25)-[:INTRODUCES]->(techBM25),
(papNomic)-[:INTRODUCES]->(techDense),

// =====================================================================
// RELATIONSHIPS — Paper -> Metric (nDCG paper defines nDCG)
// =====================================================================

(papNDCG)-[:DEFINES]->(metNDCG),

// =====================================================================
// RELATIONSHIPS — Signal(semantic) -> Paper (grounded in Nomic Embed)
// =====================================================================

(sigSemantic)-[:GROUNDED_IN]->(papNomic)

;
