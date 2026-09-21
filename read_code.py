# Import the ollama library to talk to our local AI model
import ollama

# Import os so we can build a file path that works on any operating system
import os

# Build the path to the source-code file we want the model to read
file_path = os.path.join("click", "src", "click", "types.py")

try:
    # Open and read the contents of the file
    with open(file_path, "r", encoding="utf-8") as f:
        code = f.read()
except FileNotFoundError:
    # If the file doesn't exist, print a helpful message and stop
    print(f"Could not find the file: {file_path}")
    print("Make sure you run this script from the RepoReason folder.")
    exit()

# Only keep roughly the first 6000 characters so the prompt stays
# small and the model responds quickly instead of timing out
max_chars = 6000
if len(code) > max_chars:
    code = code[:max_chars]
    print(f"(Note: the file was long, so only the first {max_chars} characters were sent to the model.)\n")

# Choose which model to use
model_name = "qwen2.5-coder:7b"

# Build the prompt: paste the code and ask for a short summary
prompt = (
    "Here is a Python source file:\n\n"
    + code
    + "\n\nSummarize in 3-4 plain sentences what this file does "
    "and list the main classes or functions it defines."
)

try:
    # Send the prompt to the model and wait for a response
    response = ollama.chat(
        model=model_name,
        messages=[{"role": "user", "content": prompt}]
    )

    # Pull out the text of the model's reply
    reply = response["message"]["content"]

    # Print the summary to the terminal
    print("Model summary:\n")
    print(reply)

except Exception as e:
    # If the model call fails (e.g. Ollama isn't running), show a friendly error
    print("Something went wrong when contacting the model.")
    print("Is Ollama running? Have you pulled the model with: ollama pull qwen2.5-coder:7b")
    print("Error details:", e)
