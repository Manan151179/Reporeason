# Import sys so we can add the project root to the import path
import sys
import os

# Add the project root (one level up from eval/) to sys.path
# so we can import retrieval.py when running from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import json to read the dataset and save results
import json

# Import re for cleaning model output
import re

# Import ollama to call the local AI model
import ollama

# Import our retrieval functions from retrieval.py
from retrieval import extract_functions, rank_functions


# --- Helper functions ---

def component(name):
    """
    Extract the component (class name) from a qualified name.
    "Choice.convert" → "Choice", "wrap_text" → "wrap_text",
    "_NumberRangeBase.convert" → "_NumberRangeBase".
    """
    # Take the part before the first dot, if there is one
    return name.split(".")[0]


def clean_prediction(raw):
    """
    Clean up the raw model output to get a function/method name.
    Strips backticks, quotes, whitespace, and takes the first line.
    Keeps a dotted name like 'Choice.convert' if present.
    """
    # Take only the first line
    text = raw.strip().splitlines()[0].strip()

    # Remove surrounding backticks and quotes
    text = text.strip("`\"'")

    # Remove a leading "FUNCTION:" label if the model added one
    if text.upper().startswith("FUNCTION:"):
        text = text[len("FUNCTION:"):].strip()

    # Remove any remaining backticks or quotes
    text = text.strip("`\"'")

    # Try to extract a dotted or plain Python identifier from the text
    match = re.search(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?", text)
    if match:
        return match.group(0)

    # Fall back to the cleaned text
    return text


def component_match(pred, gold):
    """
    Check if the component of the prediction matches the component
    of the gold answer, case-insensitively.
    """
    return component(pred).lower() == component(gold).lower()


def exact_match(pred, gold):
    """
    Check if the full qualified name matches, case-insensitively.
    """
    return pred.lower().strip() == gold.lower().strip()


# --- Condition A: LLM only (baseline) ---

def run_condition_a(bug, filepath):
    """
    Read the file (first 6000 chars), send it to the model,
    ask which function most likely needs changing.
    Returns the model's prediction as a cleaned string.
    """
    # Read the source file
    with open(filepath, "r", encoding="utf-8") as f:
        code = f.read()

    # Limit to the first 6000 characters to stay fast
    code = code[:6000]

    # Build the prompt
    prompt = (
        f"Bug: {bug}\n\n"
        f"Source file:\n\n{code}\n\n"
        "Which function or method in this file most likely needs changing "
        "to fix this bug? Reply with ONLY the fully-qualified name in the "
        "form Class.method (or just the function name for a top-level "
        "function). Nothing else."
    )

    # Call the model
    response = ollama.chat(
        model="qwen2.5-coder:7b",
        messages=[{"role": "user", "content": prompt}],
    )

    # Clean and return the prediction
    return clean_prediction(response["message"]["content"])


# --- Condition B: LLM + retrieval (proposed) ---

def run_condition_b(bug, filepath):
    """
    Use retrieval to get the top 5 functions, send only those
    to the model, ask which one most likely needs changing.
    Returns (prediction, retrieved_functions).
    """
    # Extract all functions/methods/classes from the file
    all_funcs = extract_functions(filepath)

    # Rank them by relevance to the bug using BM25
    top5 = rank_functions(bug, all_funcs, k=5)

    # Build a condensed code listing with only the top 5
    code_listing = ""
    for i, func in enumerate(top5, start=1):
        code_listing += f"--- {i}. {func['name']} (line {func['lineno']}) ---\n"
        code_listing += func["code"] + "\n\n"

    # Build the prompt
    prompt = (
        f"Bug: {bug}\n\n"
        "Here are the 5 most relevant functions/methods from the file:\n\n"
        f"{code_listing}"
        "Which one of these most likely needs changing to fix the bug? "
        "Reply with ONLY the fully-qualified name in the form Class.method "
        "(or just the function name for a top-level function). Nothing else."
    )

    # Call the model
    response = ollama.chat(
        model="qwen2.5-coder:7b",
        messages=[{"role": "user", "content": prompt}],
    )

    # Clean and return the prediction, plus the retrieved functions
    return clean_prediction(response["message"]["content"]), top5


# --- Main evaluation loop ---

if __name__ == "__main__":

    # Load the labeled dataset
    cases_path = os.path.join("eval", "cases.json")
    with open(cases_path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    total = len(cases)
    print(f"Running evaluation on {total} cases...\n")

    # Store results for each case
    results = []

    for idx, case in enumerate(cases):
        case_id = case["id"]
        bug = case["bug"]
        filepath = os.path.join(*case["file"].replace("\\", "/").split("/"))
        gold = case["gold_function"]

        print(f"Case {idx + 1}/{total}  (id={case_id})  bug: {bug[:60]}...")

        # --- Run Condition A ---
        try:
            a_pred = run_condition_a(bug, filepath)
        except Exception as e:
            print(f"  Condition A ERROR: {e}")
            a_pred = "ERROR"

        # --- Run Condition B ---
        try:
            b_pred, top5 = run_condition_b(bug, filepath)
        except Exception as e:
            print(f"  Condition B ERROR: {e}")
            b_pred = "ERROR"
            top5 = []

        # --- Scoring ---

        a_comp = component_match(a_pred, gold) if a_pred != "ERROR" else False
        b_comp = component_match(b_pred, gold) if b_pred != "ERROR" else False
        a_ex = exact_match(a_pred, gold) if a_pred != "ERROR" else False
        b_ex = exact_match(b_pred, gold) if b_pred != "ERROR" else False

        # Retrieval metric: is the gold component in the top-5 retrieved names?
        gold_comp = component(gold).lower()
        gold_in_top5 = False
        rank = 0
        for r, func in enumerate(top5, start=1):
            if component(func["name"]).lower() == gold_comp:
                gold_in_top5 = True
                rank = r
                break  # first match gives us the rank for MRR

        # Record the result
        row = {
            "id": case_id,
            "gold": gold,
            "A_prediction": a_pred,
            "A_component_correct": a_comp,
            "A_exact": a_ex,
            "B_prediction": b_pred,
            "B_component_correct": b_comp,
            "B_exact": b_ex,
            "gold_in_top5": gold_in_top5,
            "rank": rank,
        }
        results.append(row)

        print(f"  gold={gold}  A={a_pred} ({'✓' if a_comp else '✗'})  "
              f"B={b_pred} ({'✓' if b_comp else '✗'})  "
              f"top5={'✓' if gold_in_top5 else '✗'} rank={rank}")

    # --- Print per-case table ---

    print("\n" + "=" * 110)
    print(f"{'id':>3}  {'gold':<30}  {'A_pred':<28}  {'A_comp':>6}  "
          f"{'B_pred':<28}  {'B_comp':>6}  {'top5':>5}  {'rank':>4}")
    print("-" * 110)
    for r in results:
        print(f"{r['id']:>3}  {r['gold']:<30}  {r['A_prediction']:<28}  "
              f"{'✓' if r['A_component_correct'] else '✗':>6}  "
              f"{r['B_prediction']:<28}  "
              f"{'✓' if r['B_component_correct'] else '✗':>6}  "
              f"{'✓' if r['gold_in_top5'] else '✗':>5}  "
              f"{r['rank']:>4}")
    print("=" * 110)

    # --- Summary statistics ---

    n = len(results)
    a_comp_acc = sum(1 for r in results if r["A_component_correct"]) / n
    b_comp_acc = sum(1 for r in results if r["B_component_correct"]) / n
    a_exact_acc = sum(1 for r in results if r["A_exact"]) / n
    b_exact_acc = sum(1 for r in results if r["B_exact"]) / n
    recall_at_5 = sum(1 for r in results if r["gold_in_top5"]) / n
    mrr = sum((1.0 / r["rank"]) if r["rank"] > 0 else 0.0 for r in results) / n

    print("\nSummary:")
    print(f"  Condition A — component accuracy: {sum(1 for r in results if r['A_component_correct'])}/{n}  ({a_comp_acc:.1%})")
    print(f"  Condition B — component accuracy: {sum(1 for r in results if r['B_component_correct'])}/{n}  ({b_comp_acc:.1%})")
    print(f"  Condition A — exact accuracy:     {sum(1 for r in results if r['A_exact'])}/{n}  ({a_exact_acc:.1%})")
    print(f"  Condition B — exact accuracy:     {sum(1 for r in results if r['B_exact'])}/{n}  ({b_exact_acc:.1%})")
    print(f"  Retrieval  — Recall@5:            {sum(1 for r in results if r['gold_in_top5'])}/{n}  ({recall_at_5:.1%})")
    print(f"  Retrieval  — MRR:                 {mrr:.4f}")

    # --- Save results to JSON ---

    output = {
        "cases": results,
        "summary": {
            "A_component_accuracy": f"{a_comp_acc:.1%}",
            "B_component_accuracy": f"{b_comp_acc:.1%}",
            "A_exact_accuracy": f"{a_exact_acc:.1%}",
            "B_exact_accuracy": f"{b_exact_acc:.1%}",
            "retrieval_recall_at_5": f"{recall_at_5:.1%}",
            "retrieval_MRR": f"{mrr:.4f}",
        },
    }

    results_path = os.path.join("eval", "results.json")
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"\nResults saved to {results_path}")
