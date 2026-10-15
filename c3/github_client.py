# Import requests to make HTTP calls to the GitHub API
import requests

# Import os to access environment variables
import os

# Import dotenv to load the GitHub token from a .env file
from dotenv import load_dotenv


def search_repositories(query, max_results=20):
    """
    Search GitHub for repositories matching the query string.
    Returns a list of dicts with key metadata for each repo.
    """

    # Load environment variables from the .env file in the project root
    load_dotenv()

    # Read the GitHub token from the environment
    token = os.getenv("GITHUB_TOKEN")

    # If the token is missing, print a friendly message and return empty
    if not token:
        print("Error: GITHUB_TOKEN not found.")
        print("Create a .env file in the project root with:  GITHUB_TOKEN=ghp_your_token_here")
        return []

    # Set up the request headers with our token and the recommended Accept header
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }

    # The GitHub Search API returns up to 100 results per page;
    # we use per_page=max_results (capped at 100) to keep it simple
    params = {
        "q": query,
        "per_page": min(max_results, 100),
        "sort": "stars",
        "order": "desc",
    }

    # Make the API request
    url = "https://api.github.com/search/repositories"
    response = requests.get(url, headers=headers, params=params)

    # Handle common error status codes with clear messages
    if response.status_code == 401:
        print("Error 401: Bad or expired token. Check your GITHUB_TOKEN in .env.")
        return []
    elif response.status_code == 403:
        print("Error 403: Rate limit exceeded or forbidden. Wait a minute and try again.")
        print(f"  Message: {response.json().get('message', '')}")
        return []
    elif response.status_code != 200:
        print(f"Error {response.status_code}: {response.json().get('message', 'Unknown error')}")
        return []

    # Parse the JSON response
    data = response.json()

    # Build a clean list of dicts, one per repository
    repos = []
    for item in data.get("items", [])[:max_results]:

        # Extract the license SPDX ID if available, otherwise None
        license_info = item.get("license")
        license_id = license_info.get("spdx_id") if license_info else None

        repo = {
            "full_name": item.get("full_name"),
            "html_url": item.get("html_url"),
            "description": item.get("description"),
            "language": item.get("language"),
            "stars": item.get("stargazers_count", 0),
            "forks": item.get("forks_count", 0),
            "open_issues": item.get("open_issues_count", 0),
            "pushed_at": item.get("pushed_at"),
            "created_at": item.get("created_at"),
            "license": license_id,
            "topics": item.get("topics", []),
        }
        repos.append(repo)

    return repos


# --- Quick test: run this file directly to confirm real data comes back ---

if __name__ == "__main__":

    # Search for RAG-related repositories
    query = "retrieval augmented generation RAG application"
    print(f"Searching GitHub for: \"{query}\"\n")

    results = search_repositories(query, max_results=10)

    if not results:
        print("No results returned. Check the errors above.")
    else:
        print(f"Found {len(results)} repositories:\n")
        for i, repo in enumerate(results, start=1):
            # Shorten the description to 80 characters for readability
            desc = repo["description"] or "(no description)"
            if len(desc) > 80:
                desc = desc[:77] + "..."

            print(f"  {i}. {repo['full_name']}")
            print(f"     ⭐ {repo['stars']}  |  {repo['language'] or 'N/A'}  |  {desc}")
            print()
