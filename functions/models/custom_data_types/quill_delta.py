from pydantic import BaseModel, Field
from typing import Any


class QuillDelta(BaseModel):
    """Quill Delta JSON: {\"ops\": [...]} and optional keys."""
    ops: list[dict[str, Any]] = Field(default_factory=list)
