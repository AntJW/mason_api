import os
import ollama


class LLMClient:
    def __init__(self):
        self._url = os.getenv("LLM_API_URL")
        self._client = ollama.Client(host=self._url)

    @property
    def client(self):
        return self._client
