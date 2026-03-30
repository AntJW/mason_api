from pydantic import BaseModel


class Signature(BaseModel):
    id: str
    signerId: str
    signatureImageStoragePath: str
    signedAt: str  # isoformat string
