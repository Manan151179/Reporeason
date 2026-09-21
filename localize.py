# Import the ollama library to talk to our local AI model
import ollama

# Import os so we can build file paths that work on any operating system
import os

# --- Easy-to-edit settings ---

# The source file we want the model to inspect
TARGET_FILE = os.path.join("click", "src", "click", "types.py")

# A plain-English description of the bug we're investigating
BUG_DESCRIPTION = (
    "Choice options are not matching values case-insensitively "
    "when case_sensitive=False."
)

# The model we want to use
MODEL_NAME = "qwen2.5-coder:7b"

# --- Read the source file ---

try:
    # Open and read the target file
    with open(TARGET_FILE, "r", encoding="utf-8") as f:
        code = f.read()
except FileNotFoundError:
    # If the file doesn't exist, print a helpful message and stop
    print(f"Could not find the file: {TARGET_FILE}")
    print("Make sure you run this script from the RepoReason folder.")
    exit()

# Only keep roughly the first 6000 characters so the prompt stays
# small and the model responds quickly instead of timing out
MAX_CHARS = 6000
if len(code) > MAX_CHARS:
    code = code[:MAX_CHARS]
    print(f"(Note: the file was long, so only the first {MAX_CHARS} characters were sent to the model.)\n")

# --- Build the prompt ---

# Tell the model what we need: the bug, the code, and the exact reply format
prompt = (
    "I have a bug in my project.\n\n"
    f"Bug description: {BUG_DESCRIPTION}\n\n"
    "Here is the source file that may contain the problem:\n\n"
    f"{code}\n\n"
    "Based on the bug description and the code above, tell me which single "
    "function (or class method) most likely needs to be changed to fix this bug.\n\n"
    "Reply in EXACTLY this format and nothing else:\n"
    "FUNCTION: <name of the function or method>\n"
    "WHY: <1-2 sentences explaining why, referring to actual code>\n"
    "CONFIDENCE: <high, medium, or low>"
)

# --- Ask the model ---

try:
    # Send the prompt to the model and wait for a response
    response = ollama.chat(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}]
    )

    # Pull out the text of the model's reply
    reply = response["message"]["content"]

    # Print the model's answer to the terminal
    print("Model's localization result:\n")
    print(reply)

except Exception as e:
    # If the model call fails (e.g. Ollama isn't running), show a friendly error
    print("Something went wrong when contacting the model.")
    print("Is Ollama running? Have you pulled the model with: ollama pull qwen2.5-coder:7b")
    print("Error details:", e)
