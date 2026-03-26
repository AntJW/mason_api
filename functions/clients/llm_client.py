import os
import anthropic
import json
from anthropic._types import NOT_GIVEN
from anthropic.types import OutputConfigParam
from pydantic import BaseModel
from typing import Any


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

    # Parse the response into json output format based on the Pydantic model
    def parse_message(self,  system: str, messages: list[dict], output_format: BaseModel, model: str = os.getenv("LLM_MODEL"), max_tokens: int = 4096):
        response = self._client.messages.parse(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            # .parse() still accept output_format as a convenience parameter. The SDK handles the translation to output_config.format internally for Pydantic models
            output_format=output_format
        )
        return response.content[0].text


# # TODO: Use these Pydantic models to ensure response that requires Quill Delta format are returned in the correct format
# # Pydantic models for Quill Delta
# class DeltaOp(BaseModel):
#     insert: str | dict
#     attributes: dict[str, Any] | None = None
#
# class QuillDelta(BaseModel):
#     ops: list[DeltaOp]
