# Import streamlit to build our web app
import streamlit as st

# Import ollama to talk to our local AI model
import ollama

# Import os to build file paths that work on any operating system
import os

# Import re for cleaning model output
import re

# Import our retrieval functions from retrieval.py
from retrieval import extract_functions, rank_functions

# --- Configuration ---

# The model we use for localization
MODEL_NAME = "qwen2.5-coder:7b"

# If the top BM25 retrieval score is below this threshold, the evidence
# is too weak to trust — we flag it as a possible hallucination.
# This value was chosen experimentally; typical relevant hits score 5–15+.
SCORE_THRESHOLD = 2.0

# --- Page setup ---

# Set the page title shown in the browser tab
st.set_page_config(page_title="RepoReason")

# Show the app title
st.title("RepoReason")

# Show a short explanation of what this app does
st.write(
    "Describe a bug and point at a source file. The app retrieves the "
    "most relevant functions, asks the AI which one to change, and shows "
    "evidence so you can verify."
)

# --- Inputs ---

# Text box for the bug description, pre-filled with a sample bug
bug_description = st.text_area(
    "Bug description",
    value="Choice options are not matching values case-insensitively when case_sensitive=False.",
    height=100,
)

# Text box for the target file path, pre-filled with a sample path
target_file = st.text_input(
    "Target file path (relative to this project folder)",
    value="click/src/click/types.py",
)


# --- Helper: clean the model's raw output into a function name ---

def clean_prediction(raw):
    """
    Strip backticks, quotes, whitespace; take the first line;
    keep a dotted name like 'Choice.convert' if present.
    Returns a cleaned string, or the raw text if parsing fails.
    """
    # Take only the first line
    text = raw.strip().splitlines()[0].strip()

    # Remove surrounding backticks and quotes
    text = text.strip("`\"'")

    # Remove a leading "FUNCTION:" label if the model added one
    if text.upper().startswith("FUNCTION:"):
        text = text[len("FUNCTION:"):].strip()
    text = text.strip("`\"'")

    # Try to extract a dotted or plain Python identifier
    match = re.search(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?", text)
    if match:
        return match.group(0), True  # (name, parsed_ok)

    # Could not parse — return raw text
    return text, False


# --- Main logic: runs when the button is clicked ---

if st.button("Find the component to change"):

    # Make sure neither input is empty
    if not bug_description.strip() or not target_file.strip():
        st.error("Please fill in both the bug description and the file path.")
        st.stop()

    # Build an OS-friendly path from the user's input
    file_path = os.path.join(*target_file.replace("\\", "/").split("/"))

    # --- Step 1: Extract and rank functions using retrieval ---

    try:
        with st.spinner("Extracting functions from the file..."):
            all_funcs = extract_functions(file_path)
    except FileNotFoundError:
        st.error(f"Could not find the file: {file_path}")
        st.info("Make sure the path is relative to the folder where you launched the app.")
        st.stop()
    except Exception as e:
        st.error(f"Error reading the file: {e}")
        st.stop()

    # Rank functions by relevance to the bug using BM25
    top5 = rank_functions(bug_description, all_funcs, k=5)

    # --- Step 2: Hallucination guard (F5) ---
    # If the best retrieval score is below our threshold, the evidence
    # is too weak — don't bother asking the model.

    top_score = top5[0]["score"] if top5 else 0.0

    if top_score < SCORE_THRESHOLD:
        st.warning(
            "No relevant component found — the evidence is weak. "
            "Try refining the bug description or pointing at a different file."
        )
        st.stop()

    # --- Step 3: Ask the model which candidate to change ---

    # Build a condensed code listing with only the top 5
    code_listing = ""
    for i, func in enumerate(top5, start=1):
        code_listing += f"--- {i}. {func['name']} (line {func['lineno']}) ---\n"
        code_listing += func["code"] + "\n\n"

    # Prompt: ask the model to pick one candidate or say NONE
    prompt = (
        f"Bug: {bug_description}\n\n"
        "Here are the 5 most relevant functions/methods from the file:\n\n"
        f"{code_listing}"
        "Which one of these most likely needs changing to fix the bug? "
        "Reply with ONLY the fully-qualified name in the form Class.method "
        "(or just the function name for a top-level function). "
        "If none of these candidates plausibly relate to the bug, reply with "
        "exactly NONE. Nothing else."
    )

    try:
        with st.spinner("Asking the model..."):
            response = ollama.chat(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_reply = response["message"]["content"]
    except Exception as e:
        st.error("Something went wrong when contacting the model.")
        st.info("Is Ollama running? Have you pulled the model with:  ollama pull qwen2.5-coder:7b")
        st.code(str(e))
        st.stop()

    # --- Step 4: Parse the model's reply ---

    prediction, parsed_ok = clean_prediction(raw_reply)

    # Hallucination guard: if the model said NONE, stop
    if prediction.upper() == "NONE":
        st.warning(
            "No relevant component found — the evidence is weak. "
            "Try refining the bug description or the file."
        )
        st.stop()

    # --- Step 5: Ask for a short "why" explanation ---

    why_prompt = (
        f"You chose {prediction} as the function to change for this bug:\n"
        f"\"{bug_description}\"\n\n"
        "In 1–2 sentences, explain why this function needs changing, "
        "referring to actual code in it. Be concise."
    )

    why_text = ""
    try:
        with st.spinner("Getting explanation..."):
            why_response = ollama.chat(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": why_prompt}],
            )
            why_text = why_response["message"]["content"].strip()
    except Exception:
        why_text = "(Could not retrieve explanation.)"

    # --- Step 6: Derive confidence from retrieval position (F4) ---
    # We do NOT ask the model for confidence — we compute it ourselves.

    # Find the rank of the model's pick among the top 5 retrieved candidates
    pick_rank = None
    for i, func in enumerate(top5):
        # Match by component (part before the dot), case-insensitive
        pick_comp = prediction.split(".")[0].lower()
        cand_comp = func["name"].split(".")[0].lower()
        if pick_comp == cand_comp:
            pick_rank = i + 1  # 1-based rank
            break

    # Derive confidence level
    if not parsed_ok:
        # Could not parse the model's reply cleanly
        confidence = "Low"
        confidence_reason = "model output could not be parsed cleanly"
    elif top_score < SCORE_THRESHOLD * 1.5:
        # The top retrieval score is near the threshold — shaky evidence
        confidence = "Low"
        confidence_reason = f"top retrieval score ({top_score:.2f}) is near the threshold"
    elif pick_rank == 1:
        # The model picked the #1 retrieved candidate
        confidence = "High"
        confidence_reason = "model's pick is the #1 retrieved candidate"
    elif pick_rank is not None:
        # The model picked something in the top 5 but not #1
        confidence = "Medium"
        confidence_reason = f"model's pick is #{pick_rank} in retrieved candidates"
    else:
        # The model picked something not in the top 5
        confidence = "Low"
        confidence_reason = "model's pick was not found in the top-5 retrieved candidates"

    # --- Save results in session_state so they persist after button clicks (F6) ---

    st.session_state["result"] = {
        "prediction": prediction,
        "parsed_ok": parsed_ok,
        "raw_reply": raw_reply,
        "why": why_text,
        "confidence": confidence,
        "confidence_reason": confidence_reason,
        "top5": top5,
        "top_score": top_score,
    }
    # Clear any previous accept/reject status
    st.session_state.pop("review", None)


# --- Display results (persisted in session_state) ---

if "result" in st.session_state:
    r = st.session_state["result"]

    st.write("---")

    # Show the suggested component prominently
    st.subheader("Suggested component to change")
    st.code(r["prediction"])

    # Show the explanation
    st.markdown(f"**Why:** {r['why']}")

    # Show the derived confidence with its reason
    st.markdown(f"**Confidence:** {r['confidence']}  _{r['confidence_reason']}_")

    # If parsing failed, also show the raw reply
    if not r["parsed_ok"]:
        st.warning("Could not parse the model's reply cleanly. Raw output shown below:")
        st.code(r["raw_reply"])

    # --- Evidence expander: show provenance / score breakdown ---

    with st.expander("Evidence — top-5 retrieved candidates"):
        for i, func in enumerate(r["top5"], start=1):
            st.markdown(
                f"**{i}. {func['name']}** — line {func['lineno']}, "
                f"BM25 score: {func['score']:.4f}"
            )
            # Show first 15 lines of the function's code as a preview
            preview = "\n".join(func["code"].splitlines()[:15])
            st.code(preview, language="python")

    # --- Human review with persistence (F6) ---

    st.write("---")
    st.write("Do you agree with this suggestion?")

    # Two columns so the buttons sit side by side
    col1, col2 = st.columns(2)

    with col1:
        if st.button("✅ Accept"):
            st.session_state["review"] = "accepted"

    with col2:
        if st.button("❌ Reject"):
            st.session_state["review"] = "rejected"

    # Show the review status if set
    if st.session_state.get("review") == "accepted":
        st.success("Marked as accepted.")
    elif st.session_state.get("review") == "rejected":
        st.warning("Marked as rejected.")
