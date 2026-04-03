from pydantic import BaseModel, ConfigDict
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
    start: float
    end: float
    speaker: str
    text: str


class Conversation(BaseModel):
    id: str
    audioStoragePath: str
    duration: int
    header: str | None = None
    transcript: list[Transcript] | None = None
    summary: QuillDelta | None = None
    customerId: str
    status: ConversationStatus
    createdByUserId: str
    createdAt: str  # isoformat string

    # # These fields are not included in the conversation object,
    # # but are used to store the raw data from the API responses.
    # # TODO: Update transcribe to use API instead of Cloud Run service. These below fields may change or be removed then.
    # transcriptRaw: str | None = None
    # transcriptSegments: list[Transcript] | None = None
    # speakerSegments: list[Transcript] | None = None
    # summaryRaw: str | None = None
    # language: str | None = None
