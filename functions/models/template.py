from pydantic import BaseModel
from models.custom_data_types.quill_delta import QuillDelta


class Template(BaseModel):
    id: str
    name: str
    text: QuillDelta
    plainText: str
    createdAt: str  # isoformat string
    userId: str
