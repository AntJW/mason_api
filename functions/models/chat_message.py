from pydantic import BaseModel
from enum import Enum


class ChatRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(BaseModel):
    role: ChatRole
    content: str
