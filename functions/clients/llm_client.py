import os
# import ollama

import anthropic


class LLMClient:
    def __init__(self):
        # self._url = os.getenv("LLM_API_URL")
        # self._client = ollama.Client(host=self._url)

        self._client = anthropic.Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY"))

    @property
    def client(self):
        return self._client
