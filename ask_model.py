# Import the ollama library to talk to our local AI model
import ollama

# Choose which model to use
model_name = "qwen2.5-coder:7b"

# Write the prompt we want to send to the model
prompt = "Reply with one short sentence to confirm you are working."

try:
    # Send the prompt to the model and get a response
    response = ollama.chat(
        model=model_name,
        messages=[{"role": "user", "content": prompt}]
    )

    # Pull out the text of the model's reply
    reply = response["message"]["content"]

    # Print the reply to the terminal
    print("Model says:", reply)

except Exception as e:
    # If something goes wrong (e.g. Ollama isn't running), show a friendly error
    print("Something went wrong. Is Ollama running and is the model pulled?")
    print("Error details:", e)
