import os
import ollama


class LLMClient:
    def __init__(self):
        self._url = os.getenv("LLM_API_URL")
        return ollama.Client(host=self._url)
