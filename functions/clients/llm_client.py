import os
import anthropic
import json
from anthropic._types import NOT_GIVEN
from anthropic.types import OutputConfigParam


class LLMClient:
    def __init__(self):
        self._client = anthropic.Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY"))

    @property
    def client(self):
        return self._client

    def create_message(self,  system: str, messages: list[dict], output_config: OutputConfigParam | None = None, model: str = os.getenv("LLM_MODEL"), max_tokens: int = 4096):
        response = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            output_config=output_config if output_config is not None else NOT_GIVEN
        )
        return response.content[0].text

    def stream_message(self, system: str, messages: list[dict], model: str = os.getenv("LLM_MODEL"), max_tokens: int = 4096):
        with self._client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=messages
        ) as stream:
            for text in stream.text_stream:
                if text:
                    yield json.dumps(
                        {"role": "assistant", "content": text}
                    )
