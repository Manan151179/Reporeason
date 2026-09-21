# RepoReason — Test-Case Log

## Test Cases

| # | Bug description | Target file | What we check | Expected behavior | Result |
|---|----------------|-------------|---------------|-------------------|--------|
| 1 | "Choice options are not matching values case-insensitively when case_sensitive=False." | `click/src/click/types.py` | Happy path — model finds the right method and explains why. | FUNCTION names a relevant method in the `Choice` class (e.g., `convert`). WHY references case-handling logic in the code. CONFIDENCE is medium or high. | PASS — Suggested `convert`, High confidence. Correct method for Choice case-insensitive matching; explanation referenced case-sensitivity. Evidence showed real types.py code. |
| 2 | "IntRange type does not reject values that fall outside the specified min/max range." | `click/src/click/types.py` | Different bug, same file — model localizes to a different, relevant function. | FUNCTION names a method related to integer/range validation (e.g., `convert` in `IntRange`). WHY references range-checking logic. | PASS — Suggested `convert`, High confidence. Reasonable localization for numeric min/max validation (convert is where type validation happens). Evidence showed real types.py code. |
| 3 | "HelpFormatter wraps long lines incorrectly when the terminal width is very narrow." | `click/src/click/formatting.py` | Different file — model works on another file and cites evidence. | FUNCTION names a method in `HelpFormatter` related to text wrapping. Evidence section shows content from `formatting.py`. | PASS — Suggested `wrap_text`, High confidence. Correct function for the text-wrapping bug on a different file. Evidence showed real formatting.py code, incl. the wrap_text definition. |
| 4 | "broken" | `click/src/click/types.py` | Vague input — model either gives a low-confidence answer or still attempts a grounded guess. | Model does not crash. CONFIDENCE is low, or the answer is generic but still references real code. No hallucinated function names. | WEAK PASS — With the vague one-word bug ("broken"), still forced `convert` at High confidence. Answer was grounded in the file but the model showed no drop in confidence for weak input. See Finding F4. |
| 5 | "Audio playback is stuttering when the sample rate exceeds 48 kHz." | `click/src/click/types.py` | Mismatched bug — checks whether the model forces an answer (hallucination) or expresses low confidence. | Model should indicate low confidence or state that the bug does not match the file. It should NOT confidently name a function as if the bug is real for this code. | FAIL (intended) — Hallucinated a confident wrong answer on mismatched input (audio bug on a code file). See Finding F5. |
| 6 | "Choice options are not matching values case-insensitively when case_sensitive=False." | `click/src/click/does_not_exist.py` | Missing file — app shows a friendly error instead of crashing. | App displays an `st.error` message saying the file could not be found. No traceback or crash. | PASS — Non-existent file path produced a friendly "Could not find the file" message with guidance, no crash. Missing-evidence handled gracefully. |
| 7 | "Choice options are not matching values case-insensitively when case_sensitive=False." | `click/src/click/types.py` | Evidence + human review — Evidence section shows real file content; Accept/Reject buttons work. | Evidence expander shows the file path and the first ~40 lines of real code. Clicking ✅ Accept shows "Marked as accepted." Clicking ❌ Reject shows "Marked as rejected." | PASS — Evidence expander showed the real file path + code (provenance visible), so the human can verify the source. Human-review limitation found: clicking Accept re-runs the page and clears the result instead of showing a confirmation (Streamlit state not persisted). See Finding F6. |

## What we are checking

These test cases evaluate the app across five dimensions:

- **Correctness of the suggested function** — Does the model name a function that actually exists in the file and is relevant to the bug described? (Cases 1, 2, 3)
- **Grounded explanation** — Does the WHY reference actual code in the file, rather than making things up? (Cases 1, 2, 3, 4)
- **Evidence and provenance** — Does the app show the user the real code the AI looked at, so the user can verify the suggestion themselves? (Cases 3, 7)
- **Human accept/reject** — Can the user mark the suggestion as accepted or rejected, completing the human-in-the-loop workflow? (Case 7)
- **Behavior on weak or missing input** — Does the app handle vague bugs gracefully (Case 4), resist hallucination when the bug doesn't match the code (Case 5), and show a clear error when the file doesn't exist (Case 6)?

## Findings

**F4 — Confidence is always "High" (Tests 2, 4, 5).**
Across every case — a precise bug, a vague one-word bug ("broken"), and a completely mismatched bug — the model returned **High** confidence. The confidence signal is not yet meaningful: it does not go down for weak or irrelevant input. A trustworthy tool must express genuine uncertainty. Motivates a grounding/confidence step that lowers confidence (or returns "no relevant function") when evidence is weak or missing.

**F5 — Hallucination on mismatched input (Test 5).**
Given a nonsense bug ("audio playback stutters") on a text-parsing file, the model forced a confident but fabricated answer — it claimed `convert` handles "audio playback / high-volume settings," which do not exist anywhere in `types.py`, at High confidence. This is a clear hallucination: the plain LLM has no grounding mechanism to say "this bug doesn't match this file." Directly motivates evidence-grounding and code graphs.

**F6 — Result/state not preserved across button clicks (Test 7).**
Clicking Accept re-runs the Streamlit script, which clears the displayed result and returns to the empty start screen instead of confirming the choice. Evidence and provenance display correctly, but the accept/reject action does not persist. Next step: use Streamlit session state to keep the result on screen and record the human's decision.