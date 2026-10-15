# Import math for the square-root function used in cosine similarity
import math

# Import ollama to generate embeddings from a local model
import ollama


# The embedding model we use (pulled with: ollama pull nomic-embed-text)
EMBED_MODEL = "nomic-embed-text"


def embed_text(text):
    """
    Turn a string into an embedding vector (list of floats)
    using the local Ollama embedding model.
    """

    # If the text is empty, use a single space so the API doesn't fail
    if not text or not text.strip():
        text = " "

    try:
        # Call the Ollama embedding endpoint
        response = ollama.embed(model=EMBED_MODEL, input=text)
    except Exception as e:
        raise RuntimeError(
            f"Could not get an embedding. Is Ollama running? "
            f"Have you pulled the model with: ollama pull {EMBED_MODEL}\n"
            f"Error: {e}"
        )

    # The library may return the vector under different keys depending
    # on the version — handle both shapes robustly
    if "embeddings" in response and response["embeddings"]:
        # Newer format: {"embeddings": [[0.1, 0.2, ...]]}
        return response["embeddings"][0]
    elif "embedding" in response and response["embedding"]:
        # Older format: {"embedding": [0.1, 0.2, ...]}
        return response["embedding"]
    else:
        raise RuntimeError(f"Unexpected embedding response shape: {list(response.keys())}")


def cosine_similarity(a, b):
    """
    Compute the cosine similarity between two vectors (lists of floats).
    Returns a float between -1 and 1. Returns 0.0 if either vector has zero length.
    """

    # Compute the dot product of the two vectors
    dot = sum(x * y for x, y in zip(a, b))

    # Compute the magnitude (length) of each vector
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))

    # Avoid division by zero if either vector has zero length
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0

    # Cosine similarity = dot product / (magnitude_a * magnitude_b)
    return dot / (mag_a * mag_b)


# --- Quick test: embed three texts and compare similarities ---

if __name__ == "__main__":

    text1 = "retrieval augmented generation chatbot over documents"
    text2 = "RAG application for question answering on PDFs"
    text3 = "image classification deep learning web app"

    print("Embedding three texts...\n")

    vec1 = embed_text(text1)
    print(f"  Text 1: \"{text1}\"  →  {len(vec1)}-dim vector")

    vec2 = embed_text(text2)
    print(f"  Text 2: \"{text2}\"  →  {len(vec2)}-dim vector")

    vec3 = embed_text(text3)
    print(f"  Text 3: \"{text3}\"  →  {len(vec3)}-dim vector")

    # Compare text 1 with text 2 (should be high — both about RAG)
    sim_12 = cosine_similarity(vec1, vec2)
    print(f"\n  Similarity(1, 2): {sim_12:.4f}  (expect HIGH — both about RAG)")

    # Compare text 1 with text 3 (should be lower — different topics)
    sim_13 = cosine_similarity(vec1, vec3)
    print(f"  Similarity(1, 3): {sim_13:.4f}  (expect LOWER — different topics)")
