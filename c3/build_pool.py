# Import sys and os so we can add the project root to the import path
import sys
import os

# Add the project root (two levels up from c3/) to sys.path
# so we can import c3.github_client when running from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import json to read queries and save results
import json

# Import csv to write the labeling sheet safely (handles commas/newlines)
import csv

# Import time so we can pause between API calls
import time

# Import our GitHub search function
from c3.github_client import search_repositories


def main():
    # --- Load the list of queries ---

    queries_path = os.path.join("c3", "queries.json")
    with open(queries_path, "r", encoding="utf-8") as f:
        queries = json.load(f)

    print(f"Loaded {len(queries)} queries from {queries_path}\n")

    # --- Create the output folder if it doesn't exist ---

    data_dir = os.path.join("c3", "data")
    os.makedirs(data_dir, exist_ok=True)

    # This dict will hold all results, keyed by query_id
    all_results = {}

    # This list will hold every (query, repo) row for the CSV
    csv_rows = []

    # --- Fetch repos for each query ---

    for i, entry in enumerate(queries):
        query_id = entry["id"]
        query_text = entry["query"]

        print(f"[{i + 1}/{len(queries)}] Searching: \"{query_text}\" ...")

        # Call the GitHub API
        repos = search_repositories(query_text, max_results=15)

        print(f"  → Got {len(repos)} repos")

        # Store the full metadata for later ranking
        all_results[query_id] = {
            "query": query_text,
            "repos": repos,
        }

        # Add one CSV row per repo for this query
        for repo in repos:
            csv_rows.append({
                "query_id": query_id,
                "query": query_text,
                "full_name": repo["full_name"],
                "url": repo["html_url"],
                "stars": repo["stars"],
                "language": repo["language"] or "",
                "description": (repo["description"] or "")[:200],
                "relevance": "",  # left empty for human labeling
            })

        # Be gentle on the API — wait 2 seconds between queries
        if i < len(queries) - 1:
            time.sleep(2)

    # --- Save the full repo metadata to repos.json ---

    repos_path = os.path.join(data_dir, "repos.json")
    with open(repos_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)

    print(f"\nSaved full metadata to {repos_path}")

    # --- Write the labeling sheet to to_label.csv ---

    csv_path = os.path.join(data_dir, "to_label.csv")
    fieldnames = ["query_id", "query", "full_name", "url", "stars", "language", "description", "relevance"]

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)

    print(f"Saved labeling sheet to {csv_path}")

    # --- Print a summary ---

    print(f"\nSummary:")
    print(f"  Queries:          {len(queries)}")
    for entry in queries:
        qid = entry["id"]
        count = len(all_results[qid]["repos"])
        print(f"    {qid}: {count} repos")
    print(f"  Total CSV rows:   {len(csv_rows)}")


if __name__ == "__main__":
    main()
