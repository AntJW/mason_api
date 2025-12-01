import os
import ollama


class EmbeddingsAPIClient:
    def __init__(self):
        self._url = os.getenv("EMBEDDINGS_API_URL")
        self._model = os.getenv("EMBEDDINGS_MODEL")
        self._client = ollama.Client(host=self._url)

    def embed(self, text: str):
        embed_response = self._client.embed(model=self._model, input=text)
        return embed_response["embeddings"][0]
