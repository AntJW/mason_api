from pydantic import BaseModel
from enum import Enum
from models.custom_data_types.quill_delta import QuillDelta


class ConversationStatus(str, Enum):
    UPLOADED = "uploaded"
    TRANSCRIBED = "transcribed"
    SUMMARIZED = "summarized"
    COMPLETED = "completed"
    UNDEFINED = "undefined"
    ERROR = "error"


class Transcript(BaseModel):
    start: int
    end: int
    speaker: str
    text: str


class Conversation(BaseModel):
    id: str
    audioStoragePath: str
    duration: int
    createdAt: str  # isoformat string
    transcript: list[Transcript] | None = None
    header: str | None = None
    summary: QuillDelta | None = None
    customerId: str
    status: ConversationStatus
