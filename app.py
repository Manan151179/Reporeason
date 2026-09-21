# Import streamlit to build our web app
import streamlit as st

# Import ollama to talk to our local AI model
import ollama

# Import os to build file paths that work on any operating system
import os

# Set the page title shown in the browser tab
st.set_page_config(page_title="RepoReason")

# Show the app title
st.title("RepoReason")

# Show a short explanation of what this app does
st.write("Paste a bug description and a source file path, and the AI will tell you which function most likely needs changing.")

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

# A button that kicks off the analysis
if st.button("Find the function to change"):

    # Make sure neither input is empty
    if not bug_description.strip() or not target_file.strip():
        st.error("Please fill in both the bug description and the file path.")
    else:
        # --- Read the source file ---

        # Build an OS-friendly path from the user's input
        file_path = os.path.join(*target_file.replace("\\", "/").split("/"))

        try:
            # Open and read the target file
            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()
        except FileNotFoundError:
            st.error(f"Could not find the file: {file_path}")
            st.info("Make sure the path is relative to the folder where you launched the app.")
            # Stop here so the rest of the code doesn't run
            st.stop()

        # Only keep roughly the first 6000 characters so the prompt stays
        # small and the model responds quickly instead of timing out
        max_chars = 6000
        trimmed = False
        if len(code) > max_chars:
            code = code[:max_chars]
            trimmed = True

        # --- Build the prompt ---

        # Tell the model the bug, show the code, and ask for a structured answer
        prompt = (
            "I have a bug in my project.\n\n"
            f"Bug description: {bug_description}\n\n"
            "Here is the source file that may contain the problem:\n\n"
            f"{code}\n\n"
            "Based on the bug description and the code above, tell me which single "
            "function (or class method) most likely needs to be changed to fix this bug.\n\n"
            "Reply in EXACTLY this format and nothing else:\n"
            "FUNCTION: <name of the function or method>\n"
            "WHY: <1-2 sentences explaining why, referring to actual code>\n"
            "CONFIDENCE: <high, medium, or low>"
        )

        # --- Ask the model (with a spinner so the user knows it's working) ---

        try:
            with st.spinner("Thinking… this may take a moment."):
                # Send the prompt to the model and wait for a response
                response = ollama.chat(
                    model="qwen2.5-coder:7b",
                    messages=[{"role": "user", "content": prompt}],
                )

                # Pull out the text of the model's reply
                reply = response["message"]["content"]

        except Exception as e:
            st.error("Something went wrong when contacting the model.")
            st.info("Is Ollama running? Have you pulled the model with:  ollama pull qwen2.5-coder:7b")
            st.code(str(e))
            st.stop()

        # --- Display the result ---

        # Note if the file was trimmed
        if trimmed:
            st.info(f"The file was long, so only the first {max_chars} characters were sent to the model.")

        # Parse the reply to pull out FUNCTION, WHY, and CONFIDENCE lines
        function_line = ""
        why_line = ""
        confidence_line = ""
        for line in reply.splitlines():
            if line.upper().startswith("FUNCTION:"):
                function_line = line.split(":", 1)[1].strip()
            elif line.upper().startswith("WHY:"):
                why_line = line.split(":", 1)[1].strip()
            elif line.upper().startswith("CONFIDENCE:"):
                confidence_line = line.split(":", 1)[1].strip()

        # Show the suggested function prominently
        st.subheader("Suggested function to change")
        st.code(function_line if function_line else "(could not parse)")

        # Show WHY and CONFIDENCE
        st.markdown(f"**Why:** {why_line if why_line else '(could not parse)'}")
        st.markdown(f"**Confidence:** {confidence_line if confidence_line else '(could not parse)'}")

        # Show the raw model reply in case the format was unexpected
        with st.expander("Raw model reply"):
            st.text(reply)

        # --- Evidence section ---

        with st.expander("Evidence — what the AI actually looked at"):
            # Show the file path that was used
            st.markdown(f"**File:** `{file_path}`")

            # Show the first ~40 lines of the file so the user can verify
            first_lines = "\n".join(code.splitlines()[:40])
            st.code(first_lines, language="python")

        # --- Accept / Reject buttons ---

        st.write("---")
        st.write("Do you agree with the model's suggestion?")

        # Two columns so the buttons sit side by side
        col1, col2 = st.columns(2)

        with col1:
            # Accept button
            if st.button("✅ Accept"):
                st.success("Marked as accepted.")

        with col2:
            # Reject button
            if st.button("❌ Reject"):
                st.warning("Marked as rejected.")
