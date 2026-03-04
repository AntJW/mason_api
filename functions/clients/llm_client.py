import os
import anthropic


class LLMClient:
    def __init__(self):
        self._client = anthropic.Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY"))

    @property
    def client(self):
        return self._client
