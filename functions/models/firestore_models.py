from pydantic import BaseModel
from typing import Literal, Optional


class ConversationDocument(BaseModel):
    id: str
    customerId: str
    audioStoragePath: str
    duration: int
    status: Literal["uploaded", "transcribed",
                    "summarized", "completed", "error"]

    errorType: Optional[Literal["upload_failed", "transcription_failed",
                                "summarization_failed"]] = None
    errorMessage: Optional[str] = None
