# RepoReason

A small Human–AI tool that helps localize bugs to specific functions in a codebase.

## What it does

You describe a bug in plain English and point at a source file. A local AI model reads the code, suggests which single function most likely needs changing, explains why (referencing the actual code), and gives a confidence level. The app also shows you the evidence — the exact code the model looked at — so you can judge for yourself. You then accept or reject the suggestion.

## What AI capability it demonstrates

**Fault localization**: given a bug description and real source code, the model identifies *which function should change and why*, grounded in code it actually read. This is a first step toward AI-assisted debugging that a developer can verify and trust.

## Requirements

- Python 3.12
- [Ollama](https://ollama.com/) with the `qwen2.5-coder:7b` model pulled
- Python packages listed in `requirements.txt`

## Setup

1. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # macOS / Linux
   source .venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Clone the Click repository into the project folder (this is the codebase the AI reads):
   ```bash
   git clone https://github.com/pallets/click.git
   ```

4. Make sure Ollama is running and the model is pulled:
   ```bash
   ollama pull qwen2.5-coder:7b
   ```

## How to run

```bash
streamlit run app.py
```

Then open the URL shown in your terminal (usually `http://localhost:8501`) and use the web page.

## What data it uses

The [Click](https://github.com/pallets/click) repository's source files — real, senior-written Python code — serve as the codebase the AI reads and reasons about.

## Project files

- **`app.py`** — Streamlit web app. Lets you enter a bug description and file path, runs the AI, shows the result with evidence, and lets you accept or reject the suggestion.
- **`localize.py`** — Command-line script that reads a source file and asks the model which function to change, returning FUNCTION / WHY / CONFIDENCE.
- **`read_code.py`** — Command-line script that reads a source file and asks the model to summarize what the file does.
- **`ask_model.py`** — Minimal script that sends a simple prompt to the model to verify it's working.
- **`requirements.txt`** — Python dependencies (`ollama`, `streamlit`).

## What remains to be developed

This is a first vertical slice. Honest next steps include:

- **Code graphs** — build structural understanding of the code so the model can pin down the exact class (e.g., distinguishing which `convert` method among several classes).
- **Multi-file retrieval** — search across multiple files in the repository, not just one file at a time.
- **Automatic test running** — run the project's tests to confirm whether a suggested fix actually resolves the bug.
- **Memory** — save accepted/rejected suggestions so the system can learn from past sessions.
