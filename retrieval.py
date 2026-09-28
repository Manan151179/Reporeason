# Import ast to parse Python source files into syntax trees
import ast

# Import re to split text on non-alphanumeric characters
import re

# Import os to build cross-platform file paths
import os

# Import BM25Okapi for keyword-based relevance ranking
from rank_bm25 import BM25Okapi


def extract_functions(filepath):
    """
    Parse a Python file and return a list of dicts, one per
    function, method, or class, with keys: name, code, lineno.
    """

    # Read the source file
    with open(filepath, "r", encoding="utf-8") as f:
        source = f.read()

    # Parse the source into an abstract syntax tree
    tree = ast.parse(source)

    # This list will hold one dict per extracted item
    results = []

    # Walk through every top-level node in the file
    for node in ast.iter_child_nodes(tree):

        # If the node is a top-level function, extract it
        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            code = ast.get_source_segment(source, node)
            if code:
                results.append({
                    "name": node.name,
                    "code": code,
                    "lineno": node.lineno,
                })

        # If the node is a class, extract the class itself and each method
        if isinstance(node, ast.ClassDef):
            # Extract the whole class
            class_code = ast.get_source_segment(source, node)
            if class_code:
                results.append({
                    "name": node.name,
                    "code": class_code,
                    "lineno": node.lineno,
                })

            # Now extract each method inside the class
            for item in ast.iter_child_nodes(node):
                if isinstance(item, ast.FunctionDef) or isinstance(item, ast.AsyncFunctionDef):
                    method_code = ast.get_source_segment(source, item)
                    if method_code:
                        # Use a qualified name like ClassName.method_name
                        qualified_name = f"{node.name}.{item.name}"
                        results.append({
                            "name": qualified_name,
                            "code": method_code,
                            "lineno": item.lineno,
                        })

    return results


def _tokenize(text):
    """
    Lowercase the text and split it on any non-alphanumeric character.
    Returns a list of tokens.
    """
    return re.split(r"[^a-z0-9]+", text.lower())


def rank_functions(bug_description, functions, k=5):
    """
    Rank the extracted functions by relevance to the bug description
    using BM25. Returns the top-k results sorted by score descending,
    each with keys: name, code, lineno, score.
    """

    # Build the BM25 corpus: each document is the tokenized name + code
    corpus = []
    for func in functions:
        tokens = _tokenize(func["name"] + " " + func["code"])
        corpus.append(tokens)

    # Create the BM25 index from the corpus
    bm25 = BM25Okapi(corpus)

    # Tokenize the bug description as the query
    query_tokens = _tokenize(bug_description)

    # Score every function against the query
    scores = bm25.get_scores(query_tokens)

    # Attach each score to its function
    scored = []
    for i, func in enumerate(functions):
        scored.append({
            "name": func["name"],
            "code": func["code"],
            "lineno": func["lineno"],
            "score": float(scores[i]),
        })

    # Sort by score descending and return the top k
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:k]


# --- Quick test: run this file directly to see it work ---

if __name__ == "__main__":

    # Path to the file we want to analyze
    test_file = os.path.join("click", "src", "click", "types.py")

    # The bug we are investigating
    test_bug = (
        "Choice options are not matching values case-insensitively "
        "when case_sensitive=False."
    )

    print(f"File:  {test_file}")
    print(f"Bug:   {test_bug}\n")

    # Extract all functions / methods / classes from the file
    funcs = extract_functions(test_file)
    print(f"Extracted {len(funcs)} items from the file.\n")

    # Rank them by relevance to the bug
    top = rank_functions(test_bug, funcs, k=5)

    # Print the top 5 results
    print("Top 5 most relevant functions:\n")
    for i, entry in enumerate(top, start=1):
        print(f"  {i}. {entry['name']}  (line {entry['lineno']}, score {entry['score']:.4f})")
